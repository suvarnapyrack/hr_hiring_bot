from .shared_types import ResumeState
from .drive_service import fetch_from_drive
from .folder_service import fetch_from_folder
from .gmail_service import fetch_from_gmail

def choose_source(state: ResumeState) -> ResumeState:
    """Routing node (placeholder as per utils.py)."""
    return state

def run_complete_resume_analysis(jd_text="", source_type="drive", limit=5):
    """
    Main entry point for batch processing.
    """
    state = {"jd_text": jd_text, "source_type": source_type}
    if source_type == "drive": return fetch_from_drive(state, limit=limit)
    if source_type == "folder": return fetch_from_folder(state)
    if source_type == "gmail": return fetch_from_gmail(state, limit=limit)
    return []
