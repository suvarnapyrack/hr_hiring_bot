import streamlit as st

def show_ui():
    st.title("🧠 HR Hiring AI Agent (Groq + LangGraph)")
    jd_text = st.text_area("Paste Job Description", height=300)
    resume_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
    return jd_text, resume_file
