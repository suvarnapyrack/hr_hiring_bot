






# import os
# import re
# import pdfplumber
# import imaplib
# import email
# from datetime import datetime, timedelta
# from langchain_openai import OpenAIEmbeddings
# from dotenv import load_dotenv
# from sklearn.metrics.pairwise import cosine_similarity
# import json
# from dotenv import load_dotenv
# from langchain_core.prompts import PromptTemplate
# from langchain_groq import ChatGroq
# from langgraph.graph import StateGraph, END
# from langchain_openai import OpenAIEmbeddings

# # Load environment variables
# load_dotenv()
# llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY")) # llama3-70b-8192










# import pandas as pd
# import gspread
# from google.oauth2 import service_account

# SCOPES = [
#     'https://www.googleapis.com/auth/spreadsheets',
#     'https://www.googleapis.com/auth/drive'
# ]

# try:
#     creds = service_account.Credentials.from_service_account_file(
#         'credentials.json',
#         scopes=SCOPES
#     )
#     gc = gspread.authorize(creds)
#     print("✅ Google Sheets authentication successful!")

#     SHEET_ID = '10kEyz4UgkQgsxYLHyUUro3uj4Qgk63aQqlDjhiXdqLw'
#     sh = gc.open_by_key(SHEET_ID)
#     ws = sh.sheet1

#     rows = ws.get_all_records()
#     df = pd.DataFrame(rows)

#     print("\n📊 Data from sheet:")
#     print(df)

# except Exception as e:
#     print("❌ Error:", e)


# resume_links = df["resume file"].dropna().tolist()
# print(resume_links)


# def get_file_id(drive_url):
#     # Handles both ...open?id=... and .../d/FILE_ID/view
#     if "id=" in drive_url:
#         return drive_url.split("id=")[1]
#     elif "/d/" in drive_url:
#         return drive_url.split("/d/")[1].split("/")[0]
#     return None

# def convert_to_direct_download(drive_url):
#     file_id = get_file_id(drive_url)
#     if file_id:
#         return f"https://drive.google.com/uc?export=download&id={file_id}"
#     return None
# import requests
# import os

# os.makedirs("resumes/form_drive", exist_ok=True)  # folder to store files

# for i, link in enumerate(resume_links, start=1):
#     direct_url = convert_to_direct_download(link)
#     if direct_url:
#         response = requests.get(direct_url)
#         if response.status_code == 200:
#             file_path = f"resumes/form_drive/resume_{i}.pdf"
#             with open(file_path, "wb") as f:
#                 f.write(response.content)
#             print(f"✅ Downloaded: {file_path}")
#         else:
#             print(f"❌ Failed to download from {link}")


# def fetch_resumes_from_gmail(user_email, app_password, download_dir="../resumes"):
#     os.makedirs(download_dir, exist_ok=True)
#     mail = imaplib.IMAP4_SSL("imap.gmail.com")
#     mail.login(user_email, app_password)
#     mail.select("inbox")
#     date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
#     result, data = mail.search(None, f'(SINCE {date_since})')
#     email_ids = data[0].split()

#     downloaded = []
#     for eid in email_ids:
#         status, msg_data = mail.fetch(eid, "(RFC822)")
#         if status != "OK": continue
#         msg = email.message_from_bytes(msg_data[0][1])
#         subject = msg["subject"] or ""
#         if not any(kw in subject.lower() for kw in ["resume", "job", "application"]):
#             continue

#         sender_email = msg.get("From")
#         for part in msg.walk():
#             if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
#                 filename = part.get_filename()
#                 if filename and filename.lower().endswith(".pdf"):
#                     filepath = os.path.join(download_dir, filename)
#                     with open(filepath, "wb") as f:
#                         f.write(part.get_payload(decode=True))
#                     downloaded.append({
#                         "filepath": filepath,
#                         "sender_email": sender_email
#                     })
#     # mail.logout()
#     return downloaded

# import re

# def extract_mobile(text):
#     """
#     Extracts the first valid Indian mobile number from resume text.
#     Accepts formats:
#     - +91 9876543210
#     - +91-9876543210
#     - 9876543210
#     """
#     pattern = r'(\+91[-\s]?|)([6-9]\d{9})'
#     match = re.search(pattern, text)
#     if match:
#         return "+91 " + match.group(2)  # Always return in standard format
#     return "Not found"


# # -------------------- Resume Preprocessing Functions -------------------- #
# def extract_text_from_pdf(filepath):
#     # text = extract_text_from_pdf(resume_file)

#     with pdfplumber.open(filepath) as pdf:
#         text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
#     print(f"✅ PDF text extracted (first 300 chars):\n{text[:300]}")
#     return text
# # -------------------- LangGraph Node Functions -------------------- #
# def clean_text(text):
#     # Example cleaning logic, customize as needed
#     import re
#     text = re.sub(r'\s+', ' ', text)  # Remove extra whitespaces
#     text = re.sub(r'[^\x00-\x7F]+', ' ', text)  # Remove non-ASCII characters
#     return text.strip()

# def parse_resume(state):
#     raw_text = state["resume"]
#     cleaned_text = clean_text(raw_text)
#     print(f"✅ Parsed resume text (first 300 chars):\n{cleaned_text[:300]}")
#     return {**state, "resume_text": cleaned_text}
  


# import re
# import json
# from sklearn.metrics.pairwise import cosine_similarity
# from langchain.prompts import PromptTemplate

# # Add this check before doing anything
# def is_valid_resume(text):
#     if len(text.strip().split()) < 50:
#         return False
#     keywords = ['education', 'experience', 'skills', 'project', 'certification']
#     return any(kw in text.lower() for kw in keywords)

# # ------------------ Embedding Similarity ------------------
# from langchain.embeddings import HuggingFaceEmbeddings
# from sklearn.metrics.pairwise import cosine_similarity

# def embedding_similarity(jd, resume):
#     embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")


#     jd_vec = embed.embed_query(jd)
#     res_vec = embed.embed_query(resume)

#     score = cosine_similarity([jd_vec], [res_vec])[0][0]
#     print(f"✅ Embedding similarity score: {score}")
    
#     return round(score * 10, 2)  # Normalize to 0–10 scale

# # ------------------ Compute Similarity ------------------
# def compute_similarity(state):
#     jd = state["jd_text"]
#     resume = state["resume_text"]

#     if not is_valid_resume(resume):
#         return {
#             **state,
#             "llm_score": 0,
#             "embedding_score": 0,
#             "similarity_score": 0
#         }

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
#     # try:
#     #     embed_score = embedding_similarity(jd, resume)
#     # except Exception as e:
#     #     embed_score = 0
#     try:
#         embed_score = embedding_similarity(jd, resume)
#     except Exception as e:
#         print("❌ Embedding similarity failed:", str(e))
#         embed_score = 0

#     # 3. Combined score (reduced weight for embedding)
#     combined_score = round(0.4 * llm_score + 0.4 * embed_score, 2)
#     print(f"2. LLM score: {llm_score}, Embedding score: {embed_score}, Combined score: {combined_score}")
#     return {
#         **state,
#         "llm_score": llm_score,
#         "embedding_score": embed_score,
#         "similarity_score": combined_score
#     }

# # ------------------ Resume Classification ------------------
# def classify_resume(state):
#     prompt = PromptTemplate.from_template("""
#     Classify the resume below into **only one** job category from this list, based on how well it matches the provided job description:

#     - AI Engineer
#     - Data Analyst
#     - Machine Learning Engineer
#     - Data Annotator
#     - UI/UX Designer
#     - Backend Developer
#     - Frontend Developer
#     - Full Stack Developer
#     - DevOps Engineer
#     - Hr Executive
#     -Hr intern 
#     -bussiness development intern
#     -bussiness Analyst
#     -bussiness analyst intern
                                          

#     Job Description:
#     {jd}

#     Resume:
#     {resume}

#     Only return one of the above job categories exactly as-is. No explanation.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
#     print(f"3. Classified job type: {response.content.strip()}")
#     job_type = response.content.strip()
#     return {**state, "job_type": job_type}


# # ------------------ Extract Skills, Education, Experience ------------------
# def analyze_skills_education_experience(state):
#     prompt = PromptTemplate.from_template("""
# From the resume text below, extract the following and return ONLY valid JSON (no explanation or formatting):
# - Top 10 relevant skills (as a list of strings)
# - Education level (as a single string)
# - Total years of experience (as a string number)

# Resume:
# {resume}

# Respond ONLY in this JSON format:
# {{
#   "skills": ["..."],
#   "education": "...",
#   "experience": "..."
# }}""")

#     chain = prompt | llm
#     response = chain.invoke({"resume": state["resume_text"]})
    
#     print("✅ LLM raw response:\n", response.content)

#     try:
#         analysis_dict = json.loads(response.content)
#     except json.JSONDecodeError:
#         try:
#             import ast
#             analysis_dict = ast.literal_eval(response.content)
#         except Exception:
#             analysis_dict = {
#                 "skills": [],
#                 "education": "Unknown",
#                 "experience": "0"
#             }

#     print("✅ Final parsed analysis:\n", analysis_dict)

#     return {**state, "analysis": analysis_dict}


# import re

# # ✅ Threshold for relevance — adjust based on your use case
# MIN_SIMILARITY_THRESHOLD = 5 # 0 to 1 scale

# # ✅ Extract required experience from job description
# def extract_required_experience(jd_text):
#     match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
#     return int(match.group(1)) if match else None

# # ✅ Main scoring function
# def score_resume(state):
#     similarity = state.get("similarity_score", 0)
#     analysis = state.get("analysis", {})

#     # ✅ Step 1: Filter out irrelevant resumes
#     if similarity < MIN_SIMILARITY_THRESHOLD:
#         return {**state, "score": 0, "experience_filtered": False}
    

#     print(f"5. Similarity score: {similarity}")

#     # ✅ Step 2: Extract experience from resume
#     exp_str = analysis.get("experience", "0")
#     match = re.search(r"[\d.]+", exp_str)
#     exp_years = float(match.group()) if match else 0.0

#     # ✅ Step 3: Extract required experience from JD
#     required_exp = extract_required_experience(state["jd_text"])
#     if required_exp is not None and exp_years < required_exp:
#         return {**state, "score": 0, "experience_filtered": True, "ai_irrelevant": False}

#     # ✅ Step 4: Count skills
#     skills = analysis.get("skills", [])
#     skills_count = len(skills)

#     # ✅ Step 5: Normalize scores (all between 0 and 1)
#     normalized_similarity = min(similarity, 1.0)
#     normalized_exp = min(exp_years / 10.0, 1.0)
#     normalized_skills = min(skills_count / 10.0, 1.0)

#     # ✅ Step 6: Weighted score calculation (final score 0–10)
#     weighted_score = (0.5* normalized_similarity) + \
#                      (0.2 * normalized_exp) + \
#                      (0.3* normalized_skills)

#     final_score = min(weighted_score * 10.0, 10.0)

#     return {
#         **state,
#         "score": round(final_score, 2),
#         "experience_filtered": False
       
#     }



# def save_feedback(resume_id, feedback):
#     with open("feedback.json", "a") as f:
#         f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")


# def rank_top_candidates(processed_resumes):
#     # Only use already scored resumes
#     scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]

#     # Sort by score
#     scored_resumes.sort(key=lambda x: x["score"], reverse=True)

#     # Assign rank
#     for i, res in enumerate(scored_resumes, 1):
#         res["rank"] = i

#     return scored_resumes[:10]  # Change to [:2] if needed






















































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
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
import pandas as pd
import gspread

from google.oauth2 import service_account
import requests
from langchain.embeddings import HuggingFaceEmbeddings
from typing import TypedDict

# Load environment variables
load_dotenv()
llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))

# ✅ Define state to hold all pipeline data
# class ResumeState(TypedDict):
#     # Source & raw resume file
#     resume: str                     # File path or identifier
#     jd_text: str                     # Job description text
#     source_type: str                 # gmail, drive, folder, manual

#     # Extracted / parsed data
#     resume_text: str                 # Clean text from resume
#     mobile: str                      # Extracted mobile number

#     # Processing results
#     similarity_score: float          # Resume-JD similarity score
#     llm_score: float                # LLM-based similarity score
#     embedding_score: float          # Embedding-based similarity score
#     job_type: str                    # Classified job category
#     analysis: dict                   # Skills, education, and experience analysis
#     score: float                     # Final ranking score
#     experience_filtered: bool        # Whether filtered by experience
#     rank: int                       # Final ranking


# =============================================================================
# 1. SOURCE SELECTION AND FETCHING FUNCTIONS
# =============================================================================
# from app.langgraph_flow import ResumeState
from app.shared_types import ResumeState 
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.langgraph_flow import ResumeState
def choose_source(state: ResumeState) -> ResumeState:
    """
    Entry point - determines which source to use for fetching resumes
    This should be configured based on your needs
    """
    # For now, defaulting to folder source - modify as needed
    source_type = state.get("source_type", "folder")
    print(f"✅ Chosen source: {source_type}")
    return {**state, "source_type": source_type}

import os
import email
import imaplib
from datetime import datetime, timedelta
from typing import List, Dict

import os
import imaplib
import email
from datetime import datetime, timedelta
from typing import List, Dict

def fetch_resumes_from_gmail(user_email: str, app_password: str, download_dir: str = "resumes/gmail") -> list[dict]:
    """
    Fetch resumes (PDF/DOC/DOCX) from Gmail inbox in the last 7 days.
    """
    os.makedirs(download_dir, exist_ok=True)
    allowed_ext = (".pdf", ".doc", ".docx")
    downloaded = []

    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        date_since = (datetime.now() - timedelta(days=7)).strftime("%d-%b-%Y")
        result, data = mail.search(None, f'(SINCE {date_since})')

        if result != "OK":
            print("❌ Error searching mailbox")
            return []

        for eid in data[0].split():
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg.get("subject", "").lower()

            if not any(kw in subject for kw in ["resume", "job", "application"]):
                continue

            sender_email = msg.get("From")

            for part in msg.walk():
                if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
                    filename = part.get_filename()
                    if filename and filename.lower().endswith(allowed_ext):
                        filepath = os.path.join(download_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        downloaded.append({
                            "filepath": filepath,
                            "sender_email": sender_email
                        })

        # mail.logout()
        return downloaded

    except Exception as e:
        print(f"❌ Error fetching resumes from Gmail: {e}")
        return []


def fetch_from_gmail(state: dict, download_dir: str = "resumes/gmail") -> dict:
    """
    Wrapper to integrate Gmail fetch into ResumeState workflow.
    """
    user_email = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_PASS")

    if not user_email or not app_password:
        print("❌ Gmail credentials not found in environment variables.")
        return {**state, "resumes": []}

    downloaded = fetch_resumes_from_gmail(user_email, app_password, download_dir)

    if downloaded:
        print(f"✅ Successfully fetched {len(downloaded)} resumes from Gmail.")
        return {**state, "resumes": downloaded}
    else:
        print("❌ No resumes found in Gmail in the last 7 days.")
        return {**state, "resumes": []}


def fetch_from_drive(state: ResumeState) -> ResumeState:
    """
    Fetch resumes from Google Drive via Google Sheets
    """
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    def get_file_id(drive_url):
        if "id=" in drive_url:
            return drive_url.split("id=")[1]
        elif "/d/" in drive_url:
            return drive_url.split("/d/")[1].split("/")[0]
        return None

    def convert_to_direct_download(drive_url):
        file_id = get_file_id(drive_url)
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return None

    try:
        creds = service_account.Credentials.from_service_account_file(
            r'D:\hr_chatboat\credentials.json',
            scopes=SCOPES
        )
        gc = gspread.authorize(creds)
        
        SHEET_ID = '10kEyz4UgkQgsxYLHyUUro3uj4Qgk63aQqlDjhiXdqLw'
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)
        
        resume_links = df["resume file"].dropna().tolist()
        
        os.makedirs("resumes/from_drive", exist_ok=True)
        
        downloaded_resumes = []
        for i, link in enumerate(resume_links, start=1):
            direct_url = convert_to_direct_download(link)
            if direct_url:
                response = requests.get(direct_url)
                if response.status_code == 200:
                    file_path = f"resumes/from_drive/resume_{i}.pdf"
                    with open(file_path, "wb") as f:
                        f.write(response.content)
                    downloaded_resumes.append(file_path)
                    print(f"✅ Downloaded: {file_path}")
        
        if downloaded_resumes:
            # Return first resume for processing
            return {**state, "resume": downloaded_resumes[0]}
        else:
            print("❌ No resumes downloaded from Drive")
            return {**state, "resume": None}
            
    except Exception as e:
        print("❌ Error fetching from Drive:", e)
        return {**state, "resume": None}

def fetch_from_folder(state: ResumeState) -> ResumeState:
    """
    Fetch resumes from local folder
    """
    folder_path = "resumes/local"  # Adjust path as needed
    
    if not os.path.exists(folder_path):
        print(f"❌ Folder {folder_path} does not exist")
        return {**state, "resume": None}
    
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if pdf_files:
        resume_path = os.path.join(folder_path, pdf_files[0])
        print(f"✅ Fetched resume from folder: {resume_path}")
        return {**state, "resume": resume_path}
    else:
        print("❌ No PDF files found in folder")
        return {**state, "resume": None}

def manual_upload(state: ResumeState) -> ResumeState:
    """
    Handle manual file upload (placeholder for web interface)
    """
    # This would be implemented in your web interface
    print("✅ Manual upload selected")
    return state

# =============================================================================
# 2. RESUME PROCESSING FUNCTIONS
# =============================================================================

import os
import re
import pdfplumber
from typing import Dict  # Adjust if you have a custom ResumeState type


# ✅ Reusable function (can be imported anywhere)
def extract_text_from_pdf(filepath: str) -> str:
    """
    Extracts text from a PDF file using pdfplumber.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with pdfplumber.open(filepath) as pdf:
        text = "\n".join(
            [page.extract_text() for page in pdf.pages if page.extract_text()]
        )
    return text


def parse_resume(state: Dict) -> Dict:
    """
    Extracts and cleans text from a resume PDF, and retrieves the mobile number.
    """
    resume_path = state.get("resume")

    if not resume_path or not os.path.exists(resume_path):
        print("❌ Resume file not found")
        return {**state, "resume_text": "", "mobile": "Not found"}

    def clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text)  # Remove extra whitespaces
        text = re.sub(r"[^\x00-\x7F]+", " ", text)  # Remove non-ASCII characters
        return text.strip()

    def extract_mobile(text: str) -> str:
        """
        Extracts Indian mobile numbers from the text.
        """
        pattern = r"(\+91[-\s]?|)([6-9]\d{9})"
        match = re.search(pattern, text)
        return f"+91 {match.group(2)}" if match else "Not found"

    try:
        raw_text = extract_text_from_pdf(resume_path)  # ✅ Now imported from top-level
        cleaned_text = clean_text(raw_text)
        mobile = extract_mobile(cleaned_text)

        print(f"✅ Parsed resume text (first 300 chars):\n{cleaned_text[:300]}")
        print(f"✅ Extracted mobile: {mobile}")

        return {**state, "resume_text": cleaned_text, "mobile": mobile}

    except Exception as e:
        print(f"❌ Error parsing resume: {e}")
        return {**state, "resume_text": "", "mobile": "Not found"}

def compute_similarity(state: ResumeState) -> ResumeState:
    """
    Compute similarity between resume and job description
    """
    jd = state.get("jd_text", "")
    resume = state.get("resume_text", "")
    
    def is_valid_resume(text):
        if len(text.strip().split()) < 50:
            return False
        keywords = ['education', 'experience', 'skills', 'project', 'certification']
        return any(kw in text.lower() for kw in keywords)
    
    def embedding_similarity(jd, resume):
        try:
            embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            jd_vec = embed.embed_query(jd)
            res_vec = embed.embed_query(resume)
            score = cosine_similarity([jd_vec], [res_vec])[0][0]
            print(f"✅ Embedding similarity score: {score}")
            return round(score * 10, 2)  # Normalize to 0–10 scale
        except Exception as e:
            print(f"❌ Embedding similarity failed: {e}")
            return 0
    
    if not is_valid_resume(resume):
        return {
            **state,
            "llm_score": 0,
            "embedding_score": 0,
            "similarity_score": 0
        }

    # 1. LLM-based similarity
    try:
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
    except Exception as e:
        print(f"❌ LLM similarity failed: {e}")
        llm_score = 0

    # 2. Embedding-based similarity
    embed_score = embedding_similarity(jd, resume)

    # 3. Combined score
    combined_score = round(0.4 * llm_score + 0.4 * embed_score, 2)
    print(f"✅ LLM score: {llm_score}, Embedding score: {embed_score}, Combined score: {combined_score}")
    
    return {
        **state,
        "llm_score": llm_score,
        "embedding_score": embed_score,
        "similarity_score": combined_score
    }

def classify_resume(state: ResumeState) -> ResumeState:
    """
    Classify resume into job category
    """
    try:
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
        - Hr intern 
        - bussiness development intern
        - bussiness Analyst
        - bussiness analyst intern

        Job Description:
        {jd}

        Resume:
        {resume}

        Only return one of the above job categories exactly as-is. No explanation.
        """)
        chain = prompt | llm
        response = chain.invoke({"jd": state.get("jd_text", ""), "resume": state.get("resume_text", "")})
        job_type = response.content.strip()
        print(f"✅ Classified job type: {job_type}")
        return {**state, "job_type": job_type}
    except Exception as e:
        print(f"❌ Classification failed: {e}")
        return {**state, "job_type": "Unknown"}

def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """
    Extract skills, education, and experience from resume
    """
    try:
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
        response = chain.invoke({"resume": state.get("resume_text", "")})
        
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
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}

def score_resume(state: ResumeState) -> ResumeState:
    """
    Calculate final score for the resume
    """
    MIN_SIMILARITY_THRESHOLD = 5  # Adjust as needed
    
    def extract_required_experience(jd_text):
        match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
        return int(match.group(1)) if match else None
    
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})

    # Step 1: Filter out irrelevant resumes
    if similarity < MIN_SIMILARITY_THRESHOLD:
        return {**state, "score": 0, "experience_filtered": False}
    
    print(f"✅ Similarity score: {similarity}")

    # Step 2: Extract experience from resume
    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    # Step 3: Extract required experience from JD
    required_exp = extract_required_experience(state.get("jd_text", ""))
    if required_exp is not None and exp_years < required_exp:
        return {**state, "score": 0, "experience_filtered": True}

    # Step 4: Count skills
    skills = analysis.get("skills", [])
    skills_count = len(skills)

    # Step 5: Normalize scores (all between 0 and 1)
    normalized_similarity = min(similarity / 10.0, 1.0)
    normalized_exp = min(exp_years / 10.0, 1.0)
    normalized_skills = min(skills_count / 10.0, 1.0)

    # Step 6: Weighted score calculation (final score 0–10)
    weighted_score = (0.5 * normalized_similarity) + \
                     (0.2 * normalized_exp) + \
                     (0.3 * normalized_skills)

    final_score = min(weighted_score * 10.0, 10.0)

    print(f"✅ Final score: {round(final_score, 2)}")
    
    return {
        **state,
        "score": round(final_score, 2),
        "experience_filtered": False
    }

# =============================================================================
# 3. UTILITY FUNCTIONS
# =============================================================================

def save_feedback(resume_id, feedback):
    """Save feedback for a resume"""
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")

def rank_top_candidates(processed_resumes):
    """Rank candidates based on their scores"""
    # Only use already scored resumes
    scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]

    # Sort by score
    scored_resumes.sort(key=lambda x: x["score"], reverse=True)

    # Assign rank
    for i, res in enumerate(scored_resumes, 1):
        res["rank"] = i

    return scored_resumes[:10]  # Top 10 candidates












































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
