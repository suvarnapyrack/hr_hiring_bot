from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class ProcessResumesRequest(BaseModel):
    resume_items: List[Any]
    jd_text: str
    source_type: str = "manual"

class ChatRequest(BaseModel):
    question: str
