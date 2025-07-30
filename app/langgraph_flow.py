# from langchain_core.runnables import RunnableLambda
# from langgraph.graph import StateGraph, END
# from app.utils import parse_resume, compute_similarity, classify_resume, score_resume

# def build_langgraph_flow():
#     builder = StateGraph()

#     builder.add_node("parse", RunnableLambda(parse_resume))
#     builder.add_node("match", RunnableLambda(compute_similarity))
#     builder.add_node("classify", RunnableLambda(classify_resume))
#     builder.add_node("score", RunnableLambda(score_resume))

#     builder.set_entry_point("parse")
#     builder.add_edge("parse", "match")
#     builder.add_edge("match", "classify")
#     builder.add_edge("classify", "score")
#     builder.add_edge("score", END)

#     return builder.compile()


from typing import TypedDict
from langchain_core.runnables import RunnableLambda
from langgraph.graph import StateGraph, END
from app.utils import parse_resume, compute_similarity, classify_resume, score_resume, analyze_skills_education_experience


from typing import TypedDict

class ResumeState(TypedDict):
    resume: str
    jd_text: str
    resume_text: str
    similarity_score: int
    job_type: str
    analysis: str
    score: float




# -------------------- Build LangGraph -------------------- #
builder = StateGraph(ResumeState)
builder.set_entry_point("parse_resume")
builder.add_node("parse_resume", parse_resume)
builder.add_node("compute_similarity", compute_similarity)
builder.add_node("classify_resume", classify_resume)
builder.add_node("analyze_skills", analyze_skills_education_experience)
builder.add_node("score_resume", score_resume)

builder.add_edge("parse_resume", "compute_similarity")
builder.add_edge("compute_similarity", "classify_resume")
builder.add_edge("classify_resume", "analyze_skills")
builder.add_edge("analyze_skills", "score_resume")
builder.add_edge("score_resume", END)

graph = builder.compile()
