from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    email = Column(String(255), unique=True, index=True)
    mobile = Column(String(50))
    address = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Store skills as a comma-separated string for simplicity, or could be a related table
    skills = Column(Text) 
    education = Column(Text)
    experience = Column(String(100))
    stipend = Column(String(100))

    resumes = relationship("Resume", back_populates="candidate", cascade="all, delete-orphan")


class JobDescription(Base):
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True)
    job_type = Column(String(100), index=True)
    jd_text = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    resumes = relationship("Resume", back_populates="job", cascade="all, delete-orphan")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("job_descriptions.id"), nullable=True)
    
    # Local file path where the PDF is stored
    file_path = Column(String(500), nullable=False)
    source = Column(String(50)) # e.g., 'gmail', 'drive', 'local'
    
    # Analysis Scores
    similarity_score = Column(Float, default=0.0)
    final_score = Column(Float, default=0.0)
    llm_score = Column(Float, default=0.0)
    embedding_score = Column(Float, default=0.0)
    
    # LangGraph pipeline status
    status = Column(String(50), default="Pending") # Pending, Processed, Error
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    candidate = relationship("Candidate", back_populates="resumes")
    job = relationship("JobDescription", back_populates="resumes")


class JDTemplate(Base):
    """Saved Job Description templates for reuse."""
    __tablename__ = "jd_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True, nullable=False)  # Template label e.g. 'Senior Python Dev'
    job_title = Column(String(255), nullable=True)
    jd_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ChatMessage(Base):
    """Stores AI chatbot conversation history."""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    role = Column(String(50), nullable=False)   # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
