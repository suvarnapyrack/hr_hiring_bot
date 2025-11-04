





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
    score_resume
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
builder.add_node("compute_similarity", compute_similarity)
builder.add_node("classify_resume", classify_resume)
builder.add_node("analyze_skills", analyze_skills_education_experience)
builder.add_node("score_resume", score_resume)

# ✅ Edges — defining flow
builder.add_edge("choose_source", "parse_resume")
builder.add_edge("parse_resume", "compute_similarity")
builder.add_edge("compute_similarity", "classify_resume")
builder.add_edge("classify_resume", "analyze_skills")
builder.add_edge("analyze_skills", "score_resume")
builder.add_edge("score_resume", END)

# Compile graph
graph = builder.compile()
