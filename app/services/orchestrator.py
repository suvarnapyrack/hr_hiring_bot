import os
from .shared_types import ResumeState
from .core import extract_text_from_pdf
from .parser_service import parse_resume

def choose_source(state: ResumeState) -> ResumeState:
    """Routing node (placeholder as per utils.py)."""
    return state

def run_complete_resume_analysis(resume_items: list, jd_text: str, source_type: str = "manual"):
    """
    Main entry point for batch processing resumes through the LangGraph AI pipeline.
    This replaces the old `process_resumes` function from Streamlit.
    """
    all_results = []
    
    for i, item in enumerate(resume_items):
        if isinstance(item, dict):
            path = item.get("filepath") or item.get("file_path")
            sender = item.get("sender_email", "Unknown")
            filename = item.get("filename", f"resume_{i}")
        else:
            path = item
            sender = "Unknown"
            filename = f"resume_{i}"

        if not path or not os.path.exists(path):
            print(f"⚠️ File not found: {path}")
            continue

        try:
            resume_text = ""
            if path.lower().endswith('.pdf'):
                resume_text, _ = extract_text_from_pdf(path)
            elif path.lower().endswith(('.docx', '.doc')):
                with open(path, 'r', encoding='utf-8') as f:
                    resume_text = f.read()
            
            if not resume_text.strip():
                print(f"⚠️ Could not extract text from: {filename}")
                continue

            # ── BUILD INITIAL STATE ───────────────
            initial_state = {
                "source_type": source_type,
                "jd_text": jd_text,
                "resume": path,
                "resume_text": resume_text,
                "mobile": "",
                "email": "",
                "name": "",
                "similarity_score": 0,
                "llm_score": 0,
                "embedding_score": 0,
                "job_type": "",
                "analysis": {},
                "score": 0,
                "experience_filtered": False,
                "rank": 0,
                "address": ""
            }

            # ── EXECUTE PIPELINE ─────────────────
            parsed_state = parse_resume(initial_state)
            
            print(f"🔍 Processing: {filename}")
            
            from app.langgraph_flow import graph
            result_state = graph.invoke(parsed_state)

            score = result_state.get("score", 0)
            feedback = "Accept" if score >= 6.5 else "Reject"
            if result_state.get("experience_filtered", False):
                feedback = "Rejected (Experience)"

            result_data = {
                "name": result_state.get("name"),
                "email": result_state.get("email"),
                "score": score,
                "feedback": feedback,
                "mobile": result_state.get("mobile"),
                "address": result_state.get("address"),
                "resume_path": path,
                "filename": filename,
                "job_type": result_state.get("job_type", "Unknown"),
                "skills": result_state.get("analysis", {}).get("skills", []),
                "education": result_state.get("analysis", {}).get("education", "Unknown"),
                "experience": result_state.get("analysis", {}).get("experience", "0"),
                "similarity_score": result_state.get("similarity_score", 0),
                "llm_score": result_state.get("llm_score", 0),
                "embedding_score": result_state.get("embedding_score", 0),
                "resume_id": f"resume_{i}",
            }

            all_results.append(result_data)
            print(f"✅ Finished {result_state.get('name')} - Score: {score}")

        except Exception as e:
            print(f"❌ Error processing {filename}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue

    return all_results
