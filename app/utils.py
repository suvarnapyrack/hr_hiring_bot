

import os
import re
import pdfplumber
import imaplib
import email
from datetime import datetime, timedelta
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity
import json
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from langchain_openai import OpenAIEmbeddings

# Load environment variables
load_dotenv()
llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))




def fetch_resumes_from_gmail(user_email, app_password, download_dir="../resumes"):
    os.makedirs(download_dir, exist_ok=True)
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(user_email, app_password)
    mail.select("inbox")
    date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
    result, data = mail.search(None, f'(SINCE {date_since})')
    email_ids = data[0].split()

    downloaded = []
    for eid in email_ids:
        status, msg_data = mail.fetch(eid, "(RFC822)")
        if status != "OK": continue
        msg = email.message_from_bytes(msg_data[0][1])
        subject = msg["subject"] or ""
        if not any(kw in subject.lower() for kw in ["resume", "job", "application"]):
            continue

        sender_email = msg.get("From")
        for part in msg.walk():
            if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
                filename = part.get_filename()
                if filename and filename.lower().endswith(".pdf"):
                    filepath = os.path.join(download_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    downloaded.append({
                        "filepath": filepath,
                        "sender_email": sender_email
                    })
    # mail.logout()
    return downloaded

import re

def extract_mobile(text):
    """
    Extracts the first valid Indian mobile number from resume text.
    Accepts formats:
    - +91 9876543210
    - +91-9876543210
    - 9876543210
    """
    pattern = r'(\+91[-\s]?|)([6-9]\d{9})'
    match = re.search(pattern, text)
    if match:
        return "+91 " + match.group(2)  # Always return in standard format
    return "Not found"


# -------------------- Resume Preprocessing Functions -------------------- #
def extract_text_from_pdf(filepath):
    # text = extract_text_from_pdf(resume_file)

    with pdfplumber.open(filepath) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
    print(f"✅ PDF text extracted (first 300 chars):\n{text[:300]}")
    return text
# -------------------- LangGraph Node Functions -------------------- #
def clean_text(text):
    # Example cleaning logic, customize as needed
    import re
    text = re.sub(r'\s+', ' ', text)  # Remove extra whitespaces
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII characters
    return text.strip()

def parse_resume(state):
    raw_text = state["resume"]
    cleaned_text = clean_text(raw_text)  # only if needed separately
    return {**state, "resume_text": cleaned_text}
  


import re
import json
from sklearn.metrics.pairwise import cosine_similarity
from langchain.prompts import PromptTemplate

# Add this check before doing anything
def is_valid_resume(text):
    if len(text.strip().split()) < 50:
        return False
    keywords = ['education', 'experience', 'skills', 'project', 'certification']
    return any(kw in text.lower() for kw in keywords)

# ------------------ Embedding Similarity ------------------
from langchain.embeddings import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

def embedding_similarity(jd, resume):
    embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    jd_vec = embed.embed_query(jd)
    res_vec = embed.embed_query(resume)

    score = cosine_similarity([jd_vec], [res_vec])[0][0]
    print(f"1. Embedding similarity score: {score}")
    return round(score * 10, 2)  # Normalize to 0–10 scale

# ------------------ Compute Similarity ------------------
def compute_similarity(state):
    jd = state["jd_text"]
    resume = state["resume_text"]

    if not is_valid_resume(resume):
        return {
            **state,
            "llm_score": 0,
            "embedding_score": 0,
            "similarity_score": 0
        }

    # 1. LLM-based similarity
    prompt = PromptTemplate.from_template("""
    Given the job description: {jd}
    And the resume: {resume}
    How well does the resume match the job description?
    Return a score from 0 to 10.
    """)
    chain = prompt | llm
    response = chain.invoke({"jd": jd, "resume": resume})
    match = re.search(r"\b([0-9]{1,2})\b", response.content)
    llm_score = int(match.group(1)) if match else 0

    # 2. Embedding-based similarity
    try:
        embed_score = embedding_similarity(jd, resume)
    except Exception as e:
        embed_score = 0

    # 3. Combined score (reduced weight for embedding)
    combined_score = round(0.4 * llm_score + 0.4 * embed_score, 2)
    print(f"2. LLM score: {llm_score}, Embedding score: {embed_score}, Combined score: {combined_score}")
    return {
        **state,
        "llm_score": llm_score,
        "embedding_score": embed_score,
        "similarity_score": combined_score
    }

# ------------------ Resume Classification ------------------
def classify_resume(state):
    prompt = PromptTemplate.from_template("""
    Classify the resume below into **only one** job category from this list, based on how well it matches the provided job description:

    - AI Engineer
    - Data Analyst
    - Machine Learning Engineer
    - Data Annotator
    - UI/UX Designer
    - Backend Developer
    - Frontend Developer
    - Full Stack Developer
    - DevOps Engineer
    - Hr Executive
    -Hr intern 
    -bussiness development intern
    -bussiness Analyst
    -bussiness analyst intern
                                          

    Job Description:
    {jd}

    Resume:
    {resume}

    Only return one of the above job categories exactly as-is. No explanation.
    """)
    chain = prompt | llm
    response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
    print(f"3. Classified job type: {response.content.strip()}")
    job_type = response.content.strip()
    return {**state, "job_type": job_type}


# ------------------ Extract Skills, Education, Experience ------------------
def analyze_skills_education_experience(state):
    prompt = PromptTemplate.from_template("""
From the resume text below, extract the following and return ONLY valid JSON (no explanation or formatting):
- Top 10 relevant skills (as a list of strings)
- Education level (as a single string)
- Total years of experience (as a string number)

Resume:
{resume}

Respond ONLY in this JSON format:
{{
  "skills": ["..."],
  "education": "...",
  "experience": "..."
}}""")

    chain = prompt | llm
    response = chain.invoke({"resume": state["resume_text"]})
    
    print("✅ LLM raw response:\n", response.content)

    try:
        analysis_dict = json.loads(response.content)
    except json.JSONDecodeError:
        try:
            import ast
            analysis_dict = ast.literal_eval(response.content)
        except Exception:
            analysis_dict = {
                "skills": [],
                "education": "Unknown",
                "experience": "0"
            }

    print("✅ Final parsed analysis:\n", analysis_dict)

    return {**state, "analysis": analysis_dict}


import re

# ✅ Threshold for relevance — adjust based on your use case
MIN_SIMILARITY_THRESHOLD = 5 # 0 to 1 scale

# ✅ Extract required experience from job description
def extract_required_experience(jd_text):
    match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
    return int(match.group(1)) if match else None

# ✅ Main scoring function
def score_resume(state):
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})

    # ✅ Step 1: Filter out irrelevant resumes
    if similarity < MIN_SIMILARITY_THRESHOLD:
        return {**state, "score": 0, "experience_filtered": False}
    

    print(f"5. Similarity score: {similarity}")

    # ✅ Step 2: Extract experience from resume
    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    # ✅ Step 3: Extract required experience from JD
    required_exp = extract_required_experience(state["jd_text"])
    if required_exp is not None and exp_years < required_exp:
        return {**state, "score": 0, "experience_filtered": True, "ai_irrelevant": False}

    # ✅ Step 4: Count skills
    skills = analysis.get("skills", [])
    skills_count = len(skills)

    # ✅ Step 5: Normalize scores (all between 0 and 1)
    normalized_similarity = min(similarity, 1.0)
    normalized_exp = min(exp_years / 10.0, 1.0)
    normalized_skills = min(skills_count / 10.0, 1.0)

    # ✅ Step 6: Weighted score calculation (final score 0–10)
    weighted_score = (0.5* normalized_similarity) + \
                     (0.2 * normalized_exp) + \
                     (0.3* normalized_skills)

    final_score = min(weighted_score * 10.0, 10.0)

    return {
        **state,
        "score": round(final_score, 2),
        "experience_filtered": False
       
    }



def save_feedback(resume_id, feedback):
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")


def rank_top_candidates(processed_resumes):
    # Only use already scored resumes
    scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]

    # Sort by score
    scored_resumes.sort(key=lambda x: x["score"], reverse=True)

    # Assign rank
    for i, res in enumerate(scored_resumes, 1):
        res["rank"] = i

    return scored_resumes[:10]  # Change to [:2] if needed

































# import re
# import json
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain.prompts import PromptTemplate
# from langchain.embeddings import OpenAIEmbeddings

# # ✅ 1. Check if Resume is Valid
# def is_valid_resume(text):
#     if len(text.strip().split()) < 50:
#         return False
#     # Avoid hardcoding exact keywords — use broader check
#     common_sections = ['education', 'experience', 'skills', 'project', 'certification']
#     return any(section in text.lower() for section in common_sections)

# # ✅ 2. Embedding Similarity
# def embedding_similarity(jd, resume):
#     embed = OpenAIEmbeddings()
#     jd_vec = embed.embed_query(jd)
#     res_vec = embed.embed_query(resume)
#     score = cosine_similarity([jd_vec], [res_vec])[0][0]
#     return round(score * 10, 2)  # Normalize to 0–10 scale

# # ✅ 3. Compute Similarity (LLM + Embedding)
# def compute_similarity(state):
#     jd = state.get("jd_text", "")
#     resume = state.get("resume_text", "")

#     if not is_valid_resume(resume):
#         return {
#             **state,
#             "llm_score": 0,
#             "embedding_score": 0,
#             "similarity_score": 0
#         }

#     # 🧠 LLM-based similarity score
#     prompt = PromptTemplate.from_template("""
#     Given the following job description and resume, rate how well the resume matches the job description on a scale of 0 to 10.

#     Job Description:
#     {jd}

#     Resume:
#     {resume}

#     Return ONLY a number (0 to 10).
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": jd, "resume": resume})

#     # Safely extract numeric score
#     match = re.search(r"\b([0-9]{1,2})\b", response.content)
#     llm_score = int(match.group(1)) if match else 0

#     # 🤖 Embedding-based similarity
#     try:
#         embed_score = embedding_similarity(jd, resume)
#     except Exception as e:
#         embed_score = 0  # Fail-safe

#     # 🎯 Final similarity score
#     combined_score = round((0.4 * llm_score) + (0.4 * embed_score), 2)

#     return {
#         **state,
#         "llm_score": llm_score,
#         "embedding_score": embed_score,
#         "similarity_score": combined_score
#     }

# # ✅ 4. Classify Resume Role (LLM)
# def classify_resume(state):
#     prompt = PromptTemplate.from_template("""
#     Based on the job description and resume provided below, classify the resume into **only one** of the following roles:

#     - AI Engineer
#     - Data Analyst
#     - Machine Learning Engineer
#     - Data Annotator
#     - UI/UX Designer
#     - Backend Developer
#     - Frontend Developer
#     - Full Stack Developer
#     - DevOps Engineer
#     - HR Executive
#     - HR Intern
#     - Business Development Intern
#     - Business Analyst
#     - Business Analyst Intern

#     Job Description:
#     {jd}

#     Resume:
#     {resume}

#     Return only one role name from the above list. No explanation.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
#     return {**state, "job_type": response.content.strip()}

# # ✅ 5. Extract Skills, Education, Experience (LLM)
# def analyze_skills_education_experience(state):
#     prompt = PromptTemplate.from_template("""
#     From the following resume text, extract the following fields:

#     - skills: Top 10 relevant skills (as a list)
#     - education: Highest level of education (e.g., B.Tech in Computer Science)
#     - experience: Total years of professional experience (number or string like "fresher")

#     Resume:
#     {resume}

#     Return a valid JSON with keys: skills, education, experience
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"resume": state["resume_text"]})

#     try:
#         analysis_dict = json.loads(response.content)
#     except json.JSONDecodeError:
#         analysis_dict = {
#             "skills": [],
#             "education": "Unknown",
#             "experience": "0"
#         }

#     return {**state, "analysis": analysis_dict}




# import re
# import json

# MIN_SIMILARITY_THRESHOLD = 0.5  # Adjust based on testing

# # ✅ Extract required years of experience from JD
# def extract_required_experience(jd_text):
#     match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
#     return int(match.group(1)) if match else 0

# # ✅ Detect if resume mentions "fresher" or <1 year experience
# def is_fresher(exp_str):
#     exp_str = exp_str.lower().strip()
#     if "fresher" in exp_str:
#         return True
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0
#     return exp_years < 1.0

# # ✅ Main Scoring Function
# def score_resume(state):
#     similarity = state.get("similarity_score", 0.0)
#     analysis = state.get("analysis", {})
#     jd_text = state.get("jd_text", "")

#     # Step 1: Skip irrelevant resumes
#     if similarity < MIN_SIMILARITY_THRESHOLD:
#         return {**state, "score": 0, "experience_filtered": False, "ai_irrelevant": True}

#     # Step 2: Experience
#     exp_str = analysis.get("experience", "0")
#     fresher = is_fresher(exp_str)
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0

#     # Step 3: Required experience from JD
#     required_exp = extract_required_experience(jd_text)
#     if not fresher and required_exp > 0 and exp_years < required_exp:
#         return {**state, "score": 0, "experience_filtered": True, "ai_irrelevant": False}

#     # Step 4: Skills
#     skills = analysis.get("skills", [])
#     skills_count = len(skills)

#     # Step 5: Normalize
#     normalized_similarity = min(similarity, 1.0)
#     normalized_exp = 0.0 if fresher else min(exp_years / 10.0, 1.0)
#     normalized_skills = min(skills_count / 10.0, 1.0)

#     # Step 6: Weighted score (adjust based on your priority)
#     weighted_score = (0.7 * normalized_similarity) + \
#                      (0.15 * normalized_exp) + \
#                      (0.15 * normalized_skills)

#     final_score = min(weighted_score * 10.0, 10.0)

#     return {
#         **state,
#         "score": round(final_score, 2),
#         "experience_filtered": False,
#         "ai_irrelevant": False,
#         "fresher": fresher
#     }

# def save_feedback(resume_id, feedback):
#     with open("feedback.json", "a") as f:
#         f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")



# import re
# import json
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain.prompts import PromptTemplate
# from langchain.embeddings import OpenAIEmbeddings
# import streamlit as st

# # ✅ Extract name and email from resume

# def extract_name_email(resume_text):
#     email_match = re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", resume_text)
#     email = email_match.group(0) if email_match else "unknown"

#     lines = resume_text.strip().split("\n")
#     name = lines[0].strip() if lines else "Candidate"

#     return name, email

# # ✅ Check if resume text is valid
# def is_valid_resume(text):
#     if len(text.strip().split()) < 50:
#         return False
#     common_sections = ['education', 'experience', 'skills', 'project', 'certification']
#     return any(section in text.lower() for section in common_sections)

# # ✅ Embedding similarity calculation
# def embedding_similarity(jd, resume):
#     embed = OpenAIEmbeddings()
#     jd_vec = embed.embed_query(jd)
#     res_vec = embed.embed_query(resume)
#     score = cosine_similarity([jd_vec], [res_vec])[0][0]
#     return round(score * 10, 2)

# # ✅ LLM + Embedding similarity
# def compute_similarity(state):
#     jd = state.get("jd_text", "")
#     resume = state.get("resume_text", "")

#     if not is_valid_resume(resume):
#         return {**state, "llm_score": 0, "embedding_score": 0, "similarity_score": 0}

#     prompt = PromptTemplate.from_template("""
#     Given the following job description and resume, rate how well the resume matches the job description on a scale of 0 to 10.

#     Job Description:
#     {jd}

#     Resume:
#     {resume}

#     Return ONLY a number (0 to 10).
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": jd, "resume": resume})
#     match = re.search(r"\b([0-9]{1,2})\b", response.content)
#     llm_score = int(match.group(1)) if match else 0

#     try:
#         embed_score = embedding_similarity(jd, resume)
#     except Exception:
#         embed_score = 0

#     combined_score = round((0.4 * llm_score) + (0.4 * embed_score), 2)

#     return {
#         **state,
#         "llm_score": llm_score,
#         "embedding_score": embed_score,
#         "similarity_score": combined_score
#     }

# # ✅ Resume role classification (optional - if needed)
# def classify_resume(state):
#     prompt = PromptTemplate.from_template("""
#     Based on the job description and resume provided below, classify the resume into **only one** of the following roles:

#     - AI Engineer
#     - Data Analyst
#     - Machine Learning Engineer
#     - Data Annotator
#     - UI/UX Designer
#     - Backend Developer
#     - Frontend Developer
#     - Full Stack Developer
#     - DevOps Engineer
#     - HR Executive
#     - HR Intern
#     - Business Development Intern
#     - Business Analyst
#     - Business Analyst Intern

#     Job Description:
#     {jd}

#     Resume:
#     {resume}

#     Return only one role name from the above list. No explanation.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
#     return {**state, "job_type": response.content.strip()}

# # ✅ Extract top 10 skills, education, experience
# def analyze_skills_education_experience(state):
#     prompt = PromptTemplate.from_template("""
#     From the following resume text, extract the following fields:

#     - skills: Top 10 relevant skills (as a list)
#     - education: Highest level of education
#     - experience: Total years of professional experience (number or string like "fresher")

#     Resume:
#     {resume}

#     Return a valid JSON with keys: skills, education, experience
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"resume": state["resume_text"]})

#     try:
#         analysis_dict = json.loads(response.content)
#     except json.JSONDecodeError:
#         analysis_dict = {"skills": [], "education": "Unknown", "experience": "0"}

#     return {**state, "analysis": analysis_dict}

# # ✅ Extract required years of experience
# def extract_required_experience(jd_text):
#     match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
#     return int(match.group(1)) if match else 0

# # ✅ Detect fresher
# def is_fresher(exp_str):
#     exp_str = exp_str.lower().strip()
#     if "fresher" in exp_str:
#         return True
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0
#     return exp_years < 1.0

# # ✅ Scoring logic
# MIN_SIMILARITY_THRESHOLD = 0.5

# # def score_resume(state):
# #     similarity = state.get("similarity_score", 0.0)
# #     analysis = state.get("analysis", {})
# #     jd_text = state.get("jd_text", "")

# #     if similarity < MIN_SIMILARITY_THRESHOLD:
# #         return {**state, "score": 0, "experience_filtered": False, "ai_irrelevant": True}

# #     exp_str = analysis.get("experience", "0")
# #     fresher = is_fresher(exp_str)
# #     match = re.search(r"[\d.]+", exp_str)
# #     exp_years = float(match.group()) if match else 0.0

# #     required_exp = extract_required_experience(jd_text)
# #     if not fresher and required_exp > 0 and exp_years < required_exp:
# #         return {**state, "score": 0, "experience_filtered": True, "ai_irrelevant": False}

# #     skills = analysis.get("skills", [])
# #     skills_count = len(skills)

# #     normalized_similarity = min(similarity, 1.0)
# #     normalized_exp = 0.0 if fresher else min(exp_years / 10.0, 1.0)
# #     normalized_skills = min(skills_count / 10.0, 1.0)

# #     weighted_score = (0.7 * normalized_similarity) + (0.15 * normalized_exp) + (0.15 * normalized_skills)
# #     final_score = min(weighted_score * 10.0, 10.0)

# #     return {
# #         **state,
# #         "score": round(final_score, 2),
# #         "experience_filtered": False,
# #         "ai_irrelevant": False,
# #         "fresher": fresher
# #     }
# def score_resume(state):
#     similarity = state.get("similarity_score", 0.0)
#     analysis = state.get("analysis", {})
#     jd_text = state.get("jd_text", "")
#     resume_text = state.get("resume_text", "")

#     # ✅ Filter out resumes with low similarity
#     if similarity < 0.7:
#         return {
#             **state,
#             "score": 0,
#             "experience_filtered": False,
#             "ai_irrelevant": True
#         }

#     # ✅ Extract experience
#     exp_str = analysis.get("experience", "0")
#     fresher = is_fresher(exp_str)
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0

#     required_exp = extract_required_experience(jd_text)
#     if not fresher and required_exp > 0 and exp_years < required_exp:
#         return {
#             **state,
#             "score": 0,
#             "experience_filtered": True,
#             "ai_irrelevant": False
#         }

#     # ✅ Extract skills
#     skills = analysis.get("skills", [])
#     skills_count = len(skills)

#     # ✅ Keyword overlap penalty
#     jd_keywords = set(re.findall(r'\w+', jd_text.lower()))
#     resume_keywords = set(re.findall(r'\w+', resume_text.lower()))
#     keyword_overlap = jd_keywords & resume_keywords
#     overlap_score = len(keyword_overlap) / (len(jd_keywords) + 1)

#     if overlap_score < 0.03:  # If <3% of JD words found in resume
#         return {
#             **state,
#             "score": 0,
#             "experience_filtered": False,
#             "ai_irrelevant": True
#         }

#     # ✅ Normalize inputs
#     normalized_similarity = min(similarity, 1.0)
#     normalized_exp = 0.0 if fresher else min(exp_years / 10.0, 1.0)
#     normalized_skills = min(skills_count / 10.0, 1.0)

#     # ✅ Stricter weighted scoring
#     weighted_score = (
#         0.5 * normalized_similarity +
#         0.25 * normalized_exp +
#         0.25 * normalized_skills
#     )
#     final_score = round(min(weighted_score * 10.0, 10.0), 2)

#     return {
#         **state,
#         "score": final_score,
#         "experience_filtered": False,
#         "ai_irrelevant": False,
#         "fresher": fresher
#     }





# def rank_top_candidates(processed_resumes):
#     # Only use already scored resumes
#     scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]

#     # Sort by score
#     scored_resumes.sort(key=lambda x: x["score"], reverse=True)

#     # Assign rank
#     for i, res in enumerate(scored_resumes, 1):
#         res["rank"] = i

#     return scored_resumes[:4]  # Change to [:2] if needed






































































# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# import smtplib
# import os
# import streamlit as st

# def send_feedback_email(to_email, feedback_text):
#     from_email = os.getenv("GMAIL_USER")
#     app_password = os.getenv("GMAIL_PASS")

#     subject = "Feedback on Your Resume Submission"

#     if feedback_text.lower() == "accept":
#         html_body = """
#         <p>Dear Candidate,</p>
#         <p>Thank you for applying to Pyrack. We are pleased to inform you that your profile has been shortlisted for further consideration.</p>
#         <p>Our team will reach out to you shortly with the next steps.</p>
#         <p>Best regards,<br>HR Team<br>Pyrack Pvt. Ltd.</p>
#         """
#     else:
#         html_body = """
#         <p>Dear Candidate,</p>
#         <p>Thank you for your interest in Pyrack and for taking the time to apply.</p>
#         <p>After a thorough review, we regret to inform you that we will not be moving forward with your application at this stage.</p>
#         <p>We encourage you to explore future opportunities on our 
#         <a href="https://www.pyrack.com/" target="_blank">Careers Page</a>.</p>
#         <p>Wishing you all the best in your professional journey.</p>
#         <p>Sincerely,<br>HR Team<br>Pyrack Pvt. Ltd.</p>
#         """

#     # ✅ Create email with HTML content
#     msg = MIMEMultipart("alternative")
#     msg["Subject"] = subject
#     msg["From"] = from_email
#     msg["To"] = to_email
#     msg.attach(MIMEText(html_body, "html"))  # ✅ This sends HTML properly

#     print("====== EMAIL CONTENT TO BE SENT ======")
#     print(html_body)
#     print("======================================")

#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(from_email, app_password)
#             server.sendmail(from_email, to_email, msg.as_string())

#         print(f"✅ Email sent to {to_email}")
#         with open("email_log.txt", "a") as f:
#             f.write(f"Sent to {to_email} with feedback '{feedback_text}'\n")

#     except Exception as e:
#         print("❌ Failed to send email:", str(e))
#         st.error(f"❌ Email send failed: {str(e)}")
