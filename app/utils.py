

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



# -------------------- Resume Preprocessing Functions -------------------- #
def extract_text_from_pdf(filepath):
    # text = extract_text_from_pdf(resume_file)

    with pdfplumber.open(filepath) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

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
  

# def embedding_similarity(jd, resume):
#     embed = OpenAIEmbeddings()
#     jd_vec = embed.embed_query(jd)
#     res_vec = embed.embed_query(resume)
#     score = cosine_similarity([jd_vec], [res_vec])[0][0]
#     return round(score * 10, 2)  # Normalize to 0–10 scale

# def compute_similarity(state):
#     jd = state["jd_text"]
#     resume = state["resume_text"]
    
#     # 1. LLM-based similarity
#     prompt = PromptTemplate.from_template("""
#     Given the job description: {jd}
#     And the resume: {resume}
#     How well does the resume match the job description?
#     Return a score from 0 to 10.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": jd, "resume": resume})
#     match = re.search(r"\b([0-9]{1,2})\b", response.content)
#     llm_score = int(match.group(1)) if match else 0

#     # 2. Embedding-based similarity
#     try:
#         embed_score = embedding_similarity(jd, resume)
#     except Exception as e:
#         embed_score = 0  # fallback if API fails

#     # 3. Combine both scores (you can adjust the weights)
#     combined_score = round(0.5 * llm_score + 0.5 * embed_score, 2)

#     return {
#         **state,
#         "llm_score": llm_score,
#         "embedding_score": embed_score,
#         "similarity_score": combined_score
#     }

# def classify_resume(state):
#     prompt = PromptTemplate.from_template("""
#     Classify the following resume into one job category (choose one):
#     - AI Engineer
#     - Data Analyst
#     - Machine Learning Engineer
#     - Data Annotator
#     - UI/UX Designer
#     - Backend Developer
#     - Frontend Developer
#     - Full Stack Developer
#     - DevOps Engineer

#     Resume:
#     {resume}

#     Just return the category name.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"resume": state["resume_text"]})
#     return {**state, "job_type": response.content.strip()}






# def analyze_skills_education_experience(state):
#     prompt = PromptTemplate.from_template("""
#     From the following resume text, extract:
#     - Top 5 relevant skills
#     - Education level
#     - Years of experience

#     Resume:
#     {resume}
#     Just return JSON with keys: skills, education, experience
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



# def score_resume(state):
#     similarity = state.get("similarity_score", 0)
#     analysis = state.get("analysis", {})
    
#     exp_str = analysis.get("experience", "0")
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0

#     skills_count = len(analysis.get("skills", []))
    
#     score = (0.6 * similarity) + (0.2 * min(exp_years, 10)) + (0.2 * min(skills_count, 10))
#     return {**state, "score": round(score, 2)}
import re
import json
from sklearn.metrics.pairwise import cosine_similarity
from langchain.prompts import PromptTemplate
from langchain.embeddings import OpenAIEmbeddings

# Add this check before doing anything
def is_valid_resume(text):
    if len(text.strip().split()) < 50:
        return False
    keywords = ['education', 'experience', 'skills', 'project', 'certification']
    return any(kw in text.lower() for kw in keywords)

# ------------------ Embedding Similarity ------------------
def embedding_similarity(jd, resume):
    embed = OpenAIEmbeddings()
    jd_vec = embed.embed_query(jd)
    res_vec = embed.embed_query(resume)
    score = cosine_similarity([jd_vec], [res_vec])[0][0]
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

    Job Description:
    {jd}

    Resume:
    {resume}

    Only return one of the above job categories exactly as-is. No explanation.
    """)
    chain = prompt | llm
    response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
    
    job_type = response.content.strip()
    return {**state, "job_type": job_type}


# ------------------ Extract Skills, Education, Experience ------------------
def analyze_skills_education_experience(state):
    prompt = PromptTemplate.from_template("""
    From the following resume text, extract:
    - Top 5 relevant skills
    - Education level
    - Years of experience

    Resume:
    {resume}
    Just return JSON with keys: skills, education, experience
    """)
    chain = prompt | llm
    response = chain.invoke({"resume": state["resume_text"]})

    try:
        analysis_dict = json.loads(response.content)
    except json.JSONDecodeError:
        analysis_dict = {
            "skills": [],
            "education": "Unknown",
            "experience": "0"
        }

    return {**state, "analysis": analysis_dict}

# ------------------ Final Resume Scoring ------------------
# def score_resume(state):
#     similarity = state.get("similarity_score", 0)
#     analysis = state.get("analysis", {})

#     # Parse experience
#     exp_str = analysis.get("experience", "0")
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0

#     # Count skills
#     skills_count = len(analysis.get("skills", []))

#     # Final weighted score: similarity (40%) + experience (30%) + skills (30%)
#     score = (0.4 * similarity) + (0.3 * min(exp_years, 10)) + (0.3 * min(skills_count, 10))
#     return {**state, "score": round(score, 2)}
import re

# ✅ Extract required experience dynamically from JD text
def extract_required_experience(jd_text):
    match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
    return int(match.group(1)) if match else None  # None if no experience mentioned

# ✅ Resume scoring with adjusted weights
def score_resume(state):
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})
    
    # --- Extract years of experience from resume text ---
    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    # --- Extract required experience from JD ---
    required_exp = extract_required_experience(state["jd_text"])

    # ✅ If JD mentioned required experience and resume is less, filter out
    if required_exp is not None and exp_years < required_exp:
        return {**state, "score": 0, "experience_filtered": True}

    # --- Skills count ---
    skills_count = len(analysis.get("skills", []))

    # ✅ New weights: 50% similarity, 20% experience, 30% skills
    score = (0.5 * similarity) + (0.2 * min(exp_years, 10)) + (0.3 * min(skills_count, 10))

    return {
        **state,
        "score": round(score, 2),
        "experience_filtered": False
    }


def save_feedback(resume_id, feedback):
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")













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
