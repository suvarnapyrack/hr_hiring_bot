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
from app.utils import parse_resume, compute_similarity, classify_resume, score_resume

# Define a schema for state
class ResumeState(TypedDict):
    resume_text: str
    job_description: str
    match_score: float
    classification: str
    score: float

def build_langgraph_flow():
    builder = StateGraph(ResumeState)  # 🧠 Provide schema here

    builder.add_node("parse", RunnableLambda(parse_resume))
    builder.add_node("match", RunnableLambda(compute_similarity))
    builder.add_node("classify", RunnableLambda(classify_resume))
    builder.add_node("score", RunnableLambda(score_resume))

    builder.set_entry_point("parse")
    builder.add_edge("parse", "match")
    builder.add_edge("match", "classify")
    builder.add_edge("classify", "score")
    builder.add_edge("score", END)

    return builder.compile()
