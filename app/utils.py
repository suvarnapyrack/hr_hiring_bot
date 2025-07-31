

import os
import re
import pdfplumber
import imaplib
import email
from datetime import datetime, timedelta

from langchain_openai import OpenAIEmbeddings




from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

# Load environment variables
load_dotenv()
llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))


# -------------------- Gmail Resume Fetch Function -------------------- #
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
#         sender = email.utils.parseaddr(msg.get("From"))[1]

#         if not any(kw in subject.lower() for kw in ["resume", "job", "application"]):
#             continue

#         for part in msg.walk():
#             if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
#                 filename = part.get_filename()
#                 if filename and filename.lower().endswith(".pdf"):
#                     filepath = os.path.join(download_dir, filename)
#                     with open(filepath, "wb") as f:
#                         f.write(part.get_payload(decode=True))
#                     downloaded.append({
#                         "filepath": filepath,
#                         "sender_email": sender
#                     })

#     mail.logout()
#     return downloaded



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
    mail.logout()
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
    # return {**state, "resume_text": state["resume"]}
# from langchain.embeddings import OpenAIEmbeddings
from sklearn.metrics.pairwise import cosine_similarity

def embedding_similarity(jd, resume):
    embed = OpenAIEmbeddings()
    jd_vec = embed.embed_query(jd)
    res_vec = embed.embed_query(resume)
    score = cosine_similarity([jd_vec], [res_vec])[0][0]
    return round(score * 10, 2)  # Normalize to 0–10 scale

def compute_similarity(state):
    jd = state["jd_text"]
    resume = state["resume_text"]
    
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
        embed_score = 0  # fallback if API fails

    # 3. Combine both scores (you can adjust the weights)
    combined_score = round(0.5 * llm_score + 0.5 * embed_score, 2)

    return {
        **state,
        "llm_score": llm_score,
        "embedding_score": embed_score,
        "similarity_score": combined_score
    }

def classify_resume(state):
    prompt = PromptTemplate.from_template("""
    Classify the following resume into one job category (choose one):
    - AI Engineer
    - Data Analyst
    - Machine Learning Engineer
    - Data Annotator
    - UI/UX Designer
    - Backend Developer
    - Frontend Developer
    - Full Stack Developer
    - DevOps Engineer

    Resume:
    {resume}

    Just return the category name.
    """)
    chain = prompt | llm
    response = chain.invoke({"resume": state["resume_text"]})
    return {**state, "job_type": response.content.strip()}




import json

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



def score_resume(state):
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})
    
    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    skills_count = len(analysis.get("skills", []))
    
    score = (0.6 * similarity) + (0.2 * min(exp_years, 10)) + (0.2 * min(skills_count, 10))
    return {**state, "score": round(score, 2)}


def save_feedback(resume_id, feedback):
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")


# import smtplib
# from email.message import EmailMessage

# def send_feedback_email(to_email, feedback_text):
#     user = os.getenv("GMAIL_USER")
#     password = os.getenv("GMAIL_PASS")

#     msg = EmailMessage()
#     msg["Subject"] = "Resume Feedback from HR Bot"
#     msg["From"] = user
#     msg["To"] = to_email
#     msg.set_content(f"Thank you for your application.\n\nFeedback: {feedback_text}")

#     with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
#         smtp.login(user, password)
#         smtp.send_message(msg)







import smtplib
from email.mime.text import MIMEText

def send_feedback_email(to_email, feedback_text):
    from_email = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_PASS")  # App password, not regular one!

    subject = "Feedback on Your Resume Submission"
    body = f"Dear Candidate,\n\nThank you for your application.\nFeedback: {feedback_text}\n\nBest regards,\nHR Bot"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, app_password)
            server.sendmail(from_email, to_email, msg.as_string())
        print("✅ Email sent to", to_email)
    except Exception as e:
        print("❌ Failed to send email:", str(e))
