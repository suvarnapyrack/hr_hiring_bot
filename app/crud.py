from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from app.models import Candidate, JobDescription, Resume, JDTemplate, ChatMessage
from typing import List, Dict, Optional
from datetime import datetime


# ─── Candidate CRUD ───────────────────────────────────────────────────────────

def create_or_update_candidate(db: Session, candidate_data: Dict) -> Candidate:
    """Creates a new candidate or updates an existing one based on email."""
    email = candidate_data.get("email")

    if not email or email.lower() == "not found":
        candidate = Candidate(**candidate_data)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate

    candidate = db.query(Candidate).filter(Candidate.email == email).first()

    if candidate:
        if candidate_data.get("name") and candidate_data["name"] != "Not found":
            candidate.name = candidate_data["name"]
        if candidate_data.get("mobile") and candidate_data["mobile"] != "Not found":
            candidate.mobile = candidate_data["mobile"]
        if candidate_data.get("address") and candidate_data["address"] != "Not found":
            candidate.address = candidate_data["address"]
        if candidate_data.get("skills"):
            candidate.skills = candidate_data["skills"]
        if candidate_data.get("education"):
            candidate.education = candidate_data["education"]
        if candidate_data.get("experience"):
            candidate.experience = candidate_data["experience"]
        if candidate_data.get("stipend"):
            candidate.stipend = candidate_data["stipend"]
        db.commit()
        db.refresh(candidate)
        return candidate
    else:
        candidate = Candidate(**candidate_data)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
        return candidate


def create_job_description(db: Session, job_type: str, jd_text: str) -> JobDescription:
    """Creates a new job description entry if one doesn't exist for the same text."""
    job = db.query(JobDescription).filter(JobDescription.jd_text == jd_text).first()
    if job:
        return job
    job = JobDescription(job_type=job_type, jd_text=jd_text)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def save_resume_analysis(db: Session, candidate_id: int, file_path: str, source: str, result_state: Dict, job_id: Optional[int] = None) -> Resume:
    """Saves the final processed resume state into the database."""
    score = result_state.get('score', 0.0)
    hiring_status = "Accept" if score >= 6.5 else "Reject"
    if result_state.get('experience_filtered', False):
        hiring_status = "Rejected (Experience)"
        
    resume = Resume(
        candidate_id=candidate_id,
        job_id=job_id,
        file_path=file_path,
        source=source,
        similarity_score=result_state.get('similarity_score', 0.0),
        final_score=score,
        llm_score=result_state.get('llm_score', 0.0),
        embedding_score=result_state.get('embedding_score', 0.0),
        status="Processed" if score > 0 else "Error",
        hiring_status=hiring_status,
        error_message=result_state.get("error") if "error" in result_state else None
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_top_candidates(db: Session, limit: int = 50) -> List[Dict]:
    """Retrieves the top-ranked candidates based on final_score."""
    results = (
        db.query(Resume, Candidate)
        .join(Candidate, Resume.candidate_id == Candidate.id)
        .order_by(Resume.final_score.desc())
        .limit(limit)
        .all()
    )
    formatted_results = []
    for rank, (resume, candidate) in enumerate(results, start=1):
        formatted_results.append({
            "Rank": rank,
            "Name": candidate.name,
            "Email": candidate.email,
            "Mobile": candidate.mobile,
            "Final Score": round(resume.final_score, 2),
            "Similarity": round(resume.similarity_score, 2),
            "Skills": candidate.skills,
            "Experience": candidate.experience,
            "Source": resume.source,
            "Resume Path": resume.file_path,
            "Processed At": resume.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return formatted_results


# ─── Search & Filter ──────────────────────────────────────────────────────────

def search_candidates(db: Session, name: str = "", email: str = "",
                      score_min: float = 0.0, score_max: float = 10.0,
                      status: str = "All", skills_keyword: str = "") -> List[Dict]:
    """Search and filter candidates from the database."""
    query = (
        db.query(Resume, Candidate)
        .join(Candidate, Resume.candidate_id == Candidate.id)
    )

    if name:
        query = query.filter(Candidate.name.ilike(f"%{name}%"))
    if email:
        query = query.filter(Candidate.email.ilike(f"%{email}%"))
    if skills_keyword:
        query = query.filter(Candidate.skills.ilike(f"%{skills_keyword}%"))

    query = query.filter(Resume.final_score >= score_min, Resume.final_score <= score_max)

    if status == "Accepted":
        query = query.filter(Resume.final_score >= 6.5)
    elif status == "Rejected":
        query = query.filter(Resume.final_score < 6.5)

    results = query.order_by(Resume.final_score.desc()).all()

    formatted = []
    for rank, (resume, candidate) in enumerate(results, start=1):
        formatted.append({
            "Rank": rank,
            "Name": candidate.name or "N/A",
            "Email": candidate.email or "N/A",
            "Mobile": candidate.mobile or "N/A",
            "Final Score": round(resume.final_score, 2),
            "Status": "✅ Accepted" if resume.final_score >= 6.5 else "❌ Rejected",
            "Skills": candidate.skills or "",
            "Experience": candidate.experience or "N/A",
            "Education": candidate.education or "N/A",
            "Source": resume.source or "N/A",
            "Processed At": resume.created_at.strftime('%Y-%m-%d %H:%M'),
        })
    return formatted


# ─── Analytics Queries ────────────────────────────────────────────────────────

def get_score_distribution(db: Session) -> List[Dict]:
    """Raw scores for histogram."""
    rows = db.query(Resume.final_score).filter(Resume.final_score > 0).all()
    return [{"score": r[0]} for r in rows]


def get_accept_reject_counts(db: Session) -> Dict:
    """Count of accepted vs rejected candidates."""
    accepted = db.query(Resume).filter(Resume.final_score >= 6.5).count()
    rejected = db.query(Resume).filter(Resume.final_score < 6.5, Resume.final_score > 0).count()
    return {"Accepted": accepted, "Rejected": rejected}


def get_resumes_over_time(db: Session) -> List[Dict]:
    """Count of resumes processed per day."""
    rows = (
        db.query(cast(Resume.created_at, Date).label("date"), func.count(Resume.id).label("count"))
        .group_by(cast(Resume.created_at, Date))
        .order_by(cast(Resume.created_at, Date))
        .all()
    )
    return [{"date": str(r.date), "count": r.count} for r in rows]


def get_skills_frequency(db: Session, top_n: int = 15) -> List[Dict]:
    """Extract and count individual skills across all candidates."""
    rows = db.query(Candidate.skills).filter(Candidate.skills.isnot(None)).all()
    skill_counts: Dict[str, int] = {}
    for (skills_str,) in rows:
        if skills_str:
            for skill in skills_str.split(","):
                skill = skill.strip().lower()
                if skill and len(skill) > 1:
                    skill_counts[skill] = skill_counts.get(skill, 0) + 1
    sorted_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"skill": s, "count": c} for s, c in sorted_skills]


def get_source_distribution(db: Session) -> List[Dict]:
    """Count of resumes by source (gmail, manual, drive, etc.)."""
    rows = (
        db.query(Resume.source, func.count(Resume.id).label("count"))
        .group_by(Resume.source)
        .all()
    )
    return [{"source": r.source or "unknown", "count": r.count} for r in rows]


# ─── JD Template CRUD ─────────────────────────────────────────────────────────

def create_jd_template(db: Session, name: str, jd_text: str, job_title: str = "") -> JDTemplate:
    """Save a new JD template."""
    tmpl = JDTemplate(name=name, job_title=job_title, jd_text=jd_text)
    db.add(tmpl)
    db.commit()
    db.refresh(tmpl)
    return tmpl


def get_all_jd_templates(db: Session) -> List[JDTemplate]:
    """Return all saved JD templates ordered by newest first."""
    return db.query(JDTemplate).order_by(JDTemplate.created_at.desc()).all()


def delete_jd_template(db: Session, template_id: int) -> bool:
    """Delete a JD template by ID. Returns True if deleted."""
    tmpl = db.query(JDTemplate).filter(JDTemplate.id == template_id).first()
    if tmpl:
        db.delete(tmpl)
        db.commit()
        return True
    return False


# ─── Chat Message CRUD ────────────────────────────────────────────────────────

def save_chat_message(db: Session, role: str, content: str) -> ChatMessage:
    """Persist a chatbot message."""
    msg = ChatMessage(role=role, content=content)
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_chat_history(db: Session, limit: int = 50) -> List[ChatMessage]:
    """Return recent chat messages."""
    return (
        db.query(ChatMessage)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()[::-1]  # reverse so oldest first
    )


def clear_chat_history(db: Session) -> None:
    """Delete all chat messages."""
    db.query(ChatMessage).delete()
    db.commit()
