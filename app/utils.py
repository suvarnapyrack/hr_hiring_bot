import os
import pdfplumber
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

llm = ChatGroq(model="mixtral-8x7b-32768", api_key=os.getenv("GROQ_API_KEY"))

def parse_resume(state):
    resume_file = state["resume"]
    with pdfplumber.open(resume_file) as pdf:
        text = ''.join(page.extract_text() for page in pdf.pages if page.extract_text())
    return {**state, "resume_text": text}

def compute_similarity(state):
    prompt = PromptTemplate.from_template("""
    Given the job description: {jd}
    And the resume: {resume}
    How well does the resume match the job description?
    Return a score from 0 to 10.
    """)
    chain = prompt | llm
    response = chain.invoke({"jd": state["jd_text"], "resume": state["resume_text"]})
    return {**state, "similarity_score": int(response.content.strip().split()[0])}

def classify_resume(state):
    prompt = PromptTemplate.from_template("""
    Classify the following resume text into job categories like Data Analyst, AI Intern, Web Developer:
    Resume: {resume}
    """)
    chain = prompt | llm
    response = chain.invoke({"resume": state["resume_text"]})
    return {**state, "job_type": response.content.strip()}

def score_resume(state):
    final_score = 0.7 * state["similarity_score"]
    return {**state, "score": round(final_score, 2)}
