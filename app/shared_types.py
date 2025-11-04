# app/shared_types.py
from typing import TypedDict

class ResumeState(TypedDict):
    resume: str
    jd_text: str
    resume_text: str
    mobile: str
    email: str
    name: str
    similarity_score: float
    job_type: str
    analysis: dict
    score: float
    llm_score:float
    embedding_score:float
    address:str

