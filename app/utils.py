# import os
# import pdfplumber
# from langchain_core.prompts import PromptTemplate
# from langchain_groq import ChatGroq
# from dotenv import load_dotenv
# load_dotenv()
# import re

# llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))

# def parse_resume(state):
#     resume_text = state["resume"]  # already a string, not a file
#     return {**state, "resume_text": resume_text}

# def compute_similarity(state):
#     prompt = PromptTemplate.from_template("""
#     Given the job description: {jd}
#     And the resume: {resume}
#     How well does the resume match the job description?
#     Return a score from 0 to 10.
#     """)
#     chain = prompt | llm
#     response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
#     match = re.search(r"\b([0-9]{1,2})\b", response.content)
#     score = int(match.group(1)) if match else 0
#     return {**state, "similarity_score": score}
#     # return {**state, "similarity_score": int(response.content.strip().split()[0])}

# # def classify_resume(state):
# #     prompt = PromptTemplate.from_template("""
# #     Classify the following resume text into job categories like Data Analyst, AI Intern, Web Developer:
# #     Resume: {resume}
# #     """)
# #     chain = prompt | llm
# #     response = chain.invoke({"resume": state["resume_text"]})
# #     return {**state, "job_type": response.content.strip()}


# def classify_resume(state):
#     prompt = PromptTemplate.from_template("""
#     Classify the following resume into one job category (choose one):
#     - Data Analyst
#     - AI Intern
#     - Web Developer

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
#     return {**state, "analysis": response.content.strip()}

# def score_resume(state):
#     similarity = state["similarity_score"]
#     job_type = state["job_type"]
    
#     # Optional: Add skills / education / experience scores here
#     score = 0.7 * similarity  # Add more if needed
    
#     return {**state, "score": round(score, 2)}






import os
import re
import pdfplumber
import imaplib
import email
from datetime import datetime, timedelta
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv()
llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))


# -------------------- Gmail Resume Fetch Function -------------------- #
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

        for part in msg.walk():
            if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
                filename = part.get_filename()
                if filename and filename.lower().endswith(".pdf"):
                    filepath = os.path.join(download_dir, filename)
                    with open(filepath, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    downloaded.append(filepath)
    mail.logout()
    return downloaded




# -------------------- Resume Preprocessing Functions -------------------- #
def extract_text_from_pdf(filepath):
    with pdfplumber.open(filepath) as pdf:
        return "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

# -------------------- LangGraph Node Functions -------------------- #
def parse_resume(state):
    return {**state, "resume_text": state["resume"]}

def compute_similarity(state):
    prompt = PromptTemplate.from_template("""
    Given the job description: {jd}
    And the resume: {resume}
    How well does the resume match the job description?
    Return a score from 0 to 10.
    """)
    chain = prompt | llm
    response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
    match = re.search(r"\b([0-9]{1,2})\b", response.content)
    score = int(match.group(1)) if match else 0
    return {**state, "similarity_score": score}

def classify_resume(state):
    prompt = PromptTemplate.from_template("""
    Classify the following resume into one job category (choose one):
    - Data Analyst
    - AI Intern
    - Web Developer

    Resume:
    {resume}

    Just return the category name.
    """)
    chain = prompt | llm
    response = chain.invoke({"resume": state["resume_text"]})
    return {**state, "job_type": response.content.strip()}

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
    return {**state, "analysis": response.content.strip()}

def score_resume(state):
    score = 0.7 * state.get("similarity_score", 0)
    return {**state, "score": round(score, 2)}
