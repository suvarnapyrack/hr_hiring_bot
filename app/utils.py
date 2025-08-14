import mimetypes
from pathlib import Path
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


# =============================================================================
# 1. SOURCE SELECTION AND FETCHING FUNCTIONS
# =============================================================================

from app.shared_types import ResumeState 
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.langgraph_flow import ResumeState
def choose_source(state: ResumeState) -> ResumeState:#  
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


def fetch_resumes_from_gmail(user_email: str, app_password: str, download_dir: str = "resumes/gmail") -> list[dict]:
    """
    Fetch resumes (PDF/DOC/DOCX) from Gmail inbox in the last 15 days.
    """
    os.makedirs(download_dir, exist_ok=True)
    allowed_ext = (".pdf", ".doc", ".docx")
    downloaded = []

    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        date_since = (datetime.now() - timedelta(days=15)).strftime("%d-%b-%Y")
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




import pandas as pd
import gspread
import requests
import os
import re
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from pathlib import Path





def fetch_from_drive(state=None):
    """
    Fetch resumes from Google Drive via Google Sheets using Drive API.
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

    try:
        # Authenticate
        creds = service_account.Credentials.from_service_account_file(
            r'D:\hr_chatboat\credentials.json',
            scopes=SCOPES
        )

        # Read sheet
        gc = gspread.authorize(creds)
        SHEET_ID = '10kEyz4UgkQgsxYLHyUUro3uj4Qgk63aQqlDjhiXdqLw'
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)

        resume_links = df["resume file"].dropna().tolist()
        print("Resume links found:", resume_links)

        # Prepare Drive API
        drive_service = build("drive", "v3", credentials=creds)
        os.makedirs("resumes/from_drive", exist_ok=True)
        downloaded_resumes = []

        # Download each file
        for link in resume_links:
            file_id = get_file_id(link)
            if not file_id:
                print(f"❌ Could not extract file_id from: {link}")
                continue

            try:
                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

                fh.seek(0)
                file_path = Path("resumes/from_drive") / f"{file_id}.pdf"
                with open(file_path, "wb") as f:
                    f.write(fh.read())

                print(f"✅ Saved: {file_path}")
                downloaded_resumes.append(str(file_path))

            except Exception as e:
                print(f"❌ Failed to download {link}: {e}")

        return downloaded_resumes

    except Exception as e:
        print("❌ Error fetching from Drive:", e)
        return []



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
        pattern = r"(?:\+91[\s-]*|91[\s-]*|)?([6-9]\d{9})"
        match = re.search(pattern, text)
        return f"+91 {match.group(1)}" if match else "Not found"

    def extract_email(text: str) -> str:
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        match = re.search(pattern, text)
        return match.group(0) if match else "Not found"

    def extract_name(text: str) -> str:
        """
        Improved name extraction: Takes the first 2–3 words before any location or contact info.
        """
        lines = text.strip().split("\n")
        if lines:
            first_line = lines[0]
            # Remove emails and phone numbers
            first_line = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "", first_line)
            first_line = re.sub(r"(?:\+91[\s-]*|91[\s-]*|)?([6-9]\d{9})", "", first_line)
            first_line = re.sub(r"Phone:|Email:|LinkedIn:|GitHub:", "", first_line, flags=re.IGNORECASE)
            first_line = re.sub(r"\s+", " ", first_line).strip()

            # Take only the first two or three words as the name
            words = first_line.split()
            if len(words) >= 2:
                return " ".join(words[:2])  # first + last name
        return "Not found"
    try:
        raw_text = extract_text_from_pdf(resume_path)
        cleaned_text = clean_text(raw_text)

            
        
        mobile = extract_mobile(cleaned_text)
        email = extract_email(cleaned_text)
        name = extract_name(raw_text)  # Use raw text to preserve original line breaks

        print(f"✅ Parsed resume text (first 300 chars):\n{cleaned_text[:300]}")
        print(f"✅ Extracted mobile: {mobile}")
        print(f"✅ Extracted email: {email}")
        print(f"✅ Extracted name: {name}")
        print(f"...................../n..............n")

        return {**state, "resume_text": cleaned_text, "mobile": mobile, "email": email, "name": name}

    except Exception as e:
        print(f"❌ Error parsing resume: {e}")
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found"}
    
# def parse_resume(state: dict) -> dict:
#     import re
    
#     # 1️⃣ Extract text
#     raw_text = extract_text_from_pdf(state["resume_path"])
#     print("\n=== RAW TEXT (first 300 chars) ===")
#     print(raw_text[:300], "\n")

#     # 2️⃣ Clean text
#     cleaned_text = clean_text(raw_text)
#     print("\n=== CLEANED TEXT (first 300 chars) ===")
#     print(cleaned_text[:300], "\n")

#     # 3️⃣ Extract entities
#     mobile = extract_mobile(cleaned_text)
#     email = extract_email(cleaned_text)
#     name = extract_name(cleaned_text)

#     print(f"[DEBUG] Mobile Extracted: {mobile}")
#     print(f"[DEBUG] Email Extracted: {email}")
#     print(f"[DEBUG] Name Extracted: {name}")

#     # 4️⃣ Store results in state
#     state["mobile"] = mobile
#     state["email"] = email
#     state["name"] = name

#     return state

# def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
#     """
#     Extract skills, education, and experience from resume
#     """
#     try:
        
#         prompt = PromptTemplate.from_template("""
# From the resume text below, extract the following and return ONLY valid JSON (no explanation or formatting):
# - Top 10 relevant skills (as a list of strings)
# - Education level (as a single string)
# -A string representing the total years of professional work experience.Only count if explicit work experience is mentioned in a particular section (e.g., "2 years", "3.5 years", "Worked from 2019 to 2021").If the candidate is a fresher or no experience is mentioned, return "0".
# Resume:
# {resume}

# Respond ONLY in this JSON format:
# {{
#   "skills": ["..."],
#   "education": "...",
#   "experience": "..."
# }}""")

#         chain = prompt | llm
#         response = chain.invoke({"resume": state.get("resume_text", "")})
        
#         print("✅ LLM raw response:\n", response.content)

#         try:
#             analysis_dict = json.loads(response.content)
#         except json.JSONDecodeError:
#             try:
#                 import ast
#                 analysis_dict = ast.literal_eval(response.content)
#             except Exception:
#                 analysis_dict = {
#                     "skills": [],
#                     "education": "Unknown",
#                     "experience": "0"
#                 }

#         print("✅ Final parsed analysis:\n", analysis_dict)
#         return {**state, "analysis": analysis_dict}
        
#     except Exception as e:
#         print(f"❌ Analysis failed: {e}")
#         return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}
def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """
    Extract skills, education, and experience from resume
    """
    import re, json, ast

    try:
        resume_text = state.get("resume_text", "")

        prompt = PromptTemplate.from_template("""
You are an information extraction system.  
Your task is to read the resume text and extract exactly this data:  
- Top 10 relevant skills (list of strings)  
- Education level (string)  
- total_experience_years: Total professional work experience in years (string, e.g., "2", "3.5", "0")

Rules for total_experience_years:
1. Count ONLY if the resume explicitly states the duration in years/months or has start and end dates (e.g., "Aug 2024 - Dec 2024").
2. If duration is in months, convert to years with one decimal place (e.g., "5 months" → "0.4").
3. If multiple experiences are listed, sum them up.
4. Do NOT infer or guess based on skills, job titles, or education.
5. If no explicit duration is mentioned, return "0".
6. Never round up — keep the exact lower bound.

You must respond with **only valid JSON**. No explanation. No extra words.  
If a field is missing in the resume, use defaults: [] for skills, "Unknown" for education, "0" for experience.  

Resume:
{resume}

JSON response format (strictly follow this):
{
  "skills": ["Python", "TensorFlow", "..."],
  "education": "Bachelor of Pharmacy",
  "experience": "0.8"
}
""")

        chain = prompt | llm
        response = chain.invoke({"resume": resume_text})
        raw_response = response.content.strip()
        print("✅ LLM raw response:\n", raw_response)

        # Clean up potential markdown wrappers
        raw_response = re.sub(r"```(json)?", "", raw_response).strip()

        # Extract JSON portion
        if "{" in raw_response and "}" in raw_response:
            json_str = raw_response[raw_response.find("{"): raw_response.rfind("}") + 1]
        else:
            json_str = raw_response

        # Parse JSON safely
        try:
            analysis_dict = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                analysis_dict = ast.literal_eval(json_str)
            except Exception:
                analysis_dict = {
                    "skills": [],
                    "education": "Unknown",
                    "experience": "0"
                }

        # Ensure keys exist
        analysis_dict.setdefault("skills", [])
        analysis_dict.setdefault("education", "Unknown")
        analysis_dict.setdefault("experience", "0")

        print("✅ Final parsed analysis:\n", analysis_dict)
        return {**state, "analysis": analysis_dict}

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}

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
    combined_score = round(0.5 * llm_score + 0.5 * embed_score, 2)
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
        You are an information extraction system.  
        From the resume text below, extract exactly the following fields and return ONLY valid JSON (no extra words, no explanation):  

        - **skills** → Top 10 most relevant technical or professional skills (list of strings).  
        - **education** → Highest education level mentioned (string).  
        - "experience" → Calculate the total professional work experience in years (with 1 decimal precision). Follow these rules strictly:
    1. Identify all periods of professional employment from the resume.
       - Include internships only if they are labeled as work experience or have start and end dates.
       - Ignore academic projects, coursework, certifications, and volunteer activities unless labeled as work experience.
    2. For each date range:
       - Convert start and end months to numeric values.
       - If only the year is given (e.g., "2020 – 2021"), assume January for start month and December for end month.
       - If month is missing but year is given for end date, assume December.
       - If month is missing but year is given for start date, assume January.
       - If end date is "Present" or "Current", use the current month and year.
    3. Calculate the month difference, then convert to years with 1 decimal:
       - Example: 4 months → 0.3 years, 6 months → 0.5 years, 18 months → 1.5 years.
    4. If periods overlap, count the overlapping months only once.
    5. Sum all non-overlapping periods to get total experience.
    6. Output as a decimal string (e.g., "0.4", "2.0", "5.3").
    7. Never round up to the next year.

        Resume:
        {resume}

        Respond ONLY in this JSON format:
        {{
        "skills": ["Python", "TensorFlow", "..."],
        "education": "Bachelor of Pharmacy",
        "experience": "0.8"
        }}
        """)
#         prompt = PromptTemplate.from_template("""
# From the resume text below, extract the following and return ONLY valid JSON (no explanation or formatting):
# - Top 10 relevant skills (as a list of strings)
# - Education level (as a single string)
# -A string representing the total years of professional work experience.Only count if explicit work experience is mentioned in a particular section (e.g., "2 years", "3.5 years", "Worked from 2019 to 2021").If the candidate is a fresher or no experience is mentioned, return "0".
# Resume:
# {resume}

# Respond ONLY in this JSON format:
# {{
#   "skills": ["..."],
#   "education": "...",
#   "experience": "..."
# }}""")

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
