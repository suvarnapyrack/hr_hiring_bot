





from typing import TypedDict, List
from langgraph.graph import StateGraph, END
from app.utils import (
    choose_source,
    fetch_from_gmail,
    fetch_from_drive,
    fetch_from_folder,
    manual_upload,
    parse_resume,
    compute_similarity,
    classify_resume,
    analyze_skills_education_experience,
    score_resume,
    extract_text_with_ocr,
    clean_text,
    save_to_db_node
)
from app.shared_types import ResumeState

builder = StateGraph(ResumeState)

# Entry point
builder.set_entry_point("choose_source")

# Fetch nodes (optional explicit naming for clarity)
builder.add_node("choose_source", choose_source)
builder.add_node("fetch_from_gmail", fetch_from_gmail)
builder.add_node("fetch_from_drive", fetch_from_drive)
builder.add_node("fetch_from_folder", fetch_from_folder)
builder.add_node("manual_upload", manual_upload)

# Main processing nodes
builder.add_node("parse_resume", parse_resume)

def fallback_ocr_extraction(state: ResumeState) -> ResumeState:
    """Agentic Flow: Fallback node when standard extraction fails."""
    resume_path = state.get("resume")
    print(f"🤖 [Agentic Flow] Routing to OCR fallback for: {resume_path}")
    raw_text = extract_text_with_ocr(resume_path)
    cleaned_text = clean_text(raw_text) if raw_text else ""
    return {**state, "resume_text": cleaned_text, "requires_ocr": False} # Reset flag after processing

builder.add_node("fallback_ocr_extraction", fallback_ocr_extraction)
builder.add_node("compute_similarity", compute_similarity)
builder.add_node("classify_resume", classify_resume)
builder.add_node("analyze_skills", analyze_skills_education_experience)
builder.add_node("score_resume", score_resume)
builder.add_node("save_to_db", save_to_db_node)

# Agentic Flow Conditional Routing function
def route_after_parse(state: ResumeState) -> str:
    """Decide whether to proceed to scoring or fall back to OCR."""
    if state.get("requires_ocr"):
        return "fallback_ocr_extraction"
    return "compute_similarity"

# ✅ Edges — defining flow
builder.add_edge("choose_source", "parse_resume")

# Use conditional edges after parsing
builder.add_conditional_edges(
    "parse_resume",
    route_after_parse,
    {
        "fallback_ocr_extraction": "fallback_ocr_extraction",
        "compute_similarity": "compute_similarity"
    }
)

builder.add_edge("fallback_ocr_extraction", "compute_similarity")
builder.add_edge("compute_similarity", "classify_resume")
builder.add_edge("classify_resume", "analyze_skills")
builder.add_edge("analyze_skills", "score_resume")
builder.add_edge("score_resume", "save_to_db")
builder.add_edge("save_to_db", END)

# Compile graph
graph = builder.compile()
