# app/shared_types.py
from typing import TypedDict

class ResumeState(TypedDict):
    resume: str
    jd_text: str
    resume_text: str
    mobile: str
    similarity_score: float
    job_type: str
    analysis: dict
    score: float


# class ResumeState(TypedDict):
#     # Source & raw resume file
#     resume: str                     # File path or identifier
#     jd_text: str                     # Job description text

#     # Extracted / parsed data
#     resume_text: str                 # Clean text from resume
#     mobile: str                      # Extracted mobile number (string to keep leading 0)

#     # Processing results
#     similarity_score: float          # Resume-JD similarity score
#     job_type: str                    # Classified job category
#     analysis: dict                   # Skills, education, and experience analysis
#     score: float                     # Final ranking score
