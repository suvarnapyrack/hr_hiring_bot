from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import tempfile
import shutil
import builtins
import functools
from dotenv import load_dotenv

# Ensure logs are flushed immediately
builtins.print = functools.partial(print, flush=True)

# Load environment variables
load_dotenv(override=True)

from app.database import get_db
from app.api.schemas import ProcessResumesRequest, ChatRequest
from app.services.folder_service import fetch_from_folder
from app.services.drive_service import fetch_from_drive
from app.services.gmail_service import fetch_from_gmail
from app.services.upload_service import manual_upload
from app.services.orchestrator import run_complete_resume_analysis
from app.crud import get_top_candidates
from app.chatbot import get_chatbot_response

app = FastAPI(
    title="HR Hiring Bot API",
    description="API for Processing Resumes and AI HR Assistant",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/fetch/folder")
def api_fetch_folder(folder_path: str = "resumes/manual_batch", days_limit: int = 2, max_resumes: int = 10):
    try:
        # We pass a state dict, and the updated service handles the folder_path and limit
        state = fetch_from_folder({}, folder_path=folder_path, limit=max_resumes)
        items = state.get("resumes", [])
        return {"status": "success", "data": items}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fetch/drive")
def api_fetch_drive(max_resumes: int = 10):
    try:
        items = fetch_from_drive({}, limit=max_resumes)
        return {"status": "success", "data": items}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/fetch/gmail")
def api_fetch_gmail(days_limit: int = 2, max_resumes: int = 10):
    try:
        # Use fetch_from_gmail instead of fetch_resumes_from_gmail
        items_state = fetch_from_gmail({}, limit=max_resumes, days_limit=days_limit)
        items = items_state.get("resumes", [])
        return {"status": "success", "data": items}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/fetch/upload")
async def api_fetch_upload(files: List[UploadFile] = File(...)):
    try:
        temp_dir = "temp_manual"
        os.makedirs(temp_dir, exist_ok=True)
        file_paths = []
        for file in files:
            path = os.path.join(temp_dir, file.filename)
            with open(path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_paths.append(path)
        items = manual_upload(file_paths)
        return {"status": "success", "data": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process")
def api_process_resumes(request: ProcessResumesRequest, db: Session = Depends(get_db)):
    try:
        results = run_complete_resume_analysis(
            resume_items=request.resume_items, 
            jd_text=request.jd_text, 
            source_type=request.source_type
        )
        return {"status": "success", "data": results}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/candidates/top")
def get_top_ranked_candidates(limit: int = 50, db: Session = Depends(get_db)):
    try:
        candidates = get_top_candidates(db, limit=limit)
        return {"status": "success", "data": candidates}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
def ask_ai_chatbot(request: ChatRequest, db: Session = Depends(get_db)):
    try:
        answer = get_chatbot_response(request.question, db)
        return {"status": "success", "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
