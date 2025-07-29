import streamlit as st
from app.ui import show_ui
from app.langgraph_flow import build_langgraph_flow

graph = build_langgraph_flow()

def run():
    jd_text, resume_file = show_ui()
    if st.button("🧠 Run Screening") and jd_text and resume_file:
        state = {"jd_text": jd_text, "resume": resume_file}
        result = graph.invoke(state)
        st.success("✅ Resume Processed")
        st.write("📌 Job Type:", result['job_type'])
        st.write("📊 Similarity Score:", result['similarity_score'])
        st.write("🏆 Final Score:", result['score'])

if __name__ == "__main__":
    run()
