import os
from .shared_types import ResumeState

def fetch_from_folder(state: ResumeState) -> ResumeState:
    """
    Fetch resumes from local folder.
    """
    download_dir = "resumes/manual_batch"
    os.makedirs(download_dir, exist_ok=True)
    
    resumes = []
    for filename in os.listdir(download_dir):
        if filename.lower().endswith((".pdf", ".doc", ".docx")):
            resumes.append({
                "filepath": os.path.join(download_dir, filename),
                "source": "folder"
            })
            
    print(f"✅ Found {len(resumes)} resumes in folder.")
    return {**state, "resumes": resumes}
