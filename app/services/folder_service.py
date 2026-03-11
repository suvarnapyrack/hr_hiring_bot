import os
from .shared_types import ResumeState

def fetch_from_folder(state: ResumeState, folder_path: str = "resumes/manual_batch", limit: int = 10) -> ResumeState:
    """
    Fetch resumes from local folder.
    """
    os.makedirs(folder_path, exist_ok=True)
    
    resumes = []
    for filename in os.listdir(folder_path):
        if filename.lower().endswith((".pdf", ".doc", ".docx")):
            resumes.append({
                "filepath": os.path.join(folder_path, filename),
                "filename": filename,
                "source": "folder"
            })
    
    if limit and len(resumes) > limit:
        resumes = resumes[:limit]
            
    print(f"✅ Found {len(resumes)} resumes in folder: {folder_path}")
    return {**state, "resumes": resumes}
