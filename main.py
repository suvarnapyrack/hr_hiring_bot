


















import os
import re
import pdfplumber
import imaplib
import email
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.langgraph_flow import graph
from app.utils import fetch_resumes_from_gmail, extract_text_from_pdf, send_feedback_email


load_dotenv()



# def process_resumes(resume_items, jd_text):
#     all_results = []

#     for i, item in enumerate(resume_items):
#         path = item["filepath"]
#         sender = item["sender_email"]

#         resume_text = extract_text_from_pdf(path)
#         state = {
#             "jd_text": jd_text,
#             "resume_path": path,
#             "resume": resume_text,
#             "resume_id": f"resume_{i}",
#             "sender_email": sender
#         }

#         result = graph.invoke(state)
#         result["sender_email"] = sender  # store email for later feedback
#         all_results.append(result)

#     return all_results

# # -------------------- Streamlit UI -------------------- #
# def run_streamlit():
#     st.set_page_config(page_title="HR Hiring Bot", layout="centered")
#     st.title("🤖 HR Hiring Bot")

#     menu_option = st.sidebar.radio("Select Mode", ["📩 Gmail Fetch", "📁 Upload Folder", "🧠 Manual Upload"])

#     jd_text = st.text_area("📄 Paste Job Description here")

#     if not jd_text:
#         st.warning("Please enter a job description to proceed.")
#         return
    
#     resume_items = []

# # Option 1: Gmail Fetch
#     if menu_option == "📩 Gmail Fetch":
#         if st.button("📥 Fetch from Gmail"):
#             user = os.getenv("GMAIL_USER")
#             password = os.getenv("GMAIL_PASS")
#             if not user or not password:
#                 st.error("❌ Gmail credentials not found in .env")
#             else:
#                 resume_items = fetch_resumes_from_gmail(user, password)

#         if resume_items:
#             st.success(f"✅ Fetched {len(resume_items)} resumes")

#             st.info("⏳ Analyzing fetched resumes...")
#             results = process_resumes(resume_items, jd_text)

#             for i, res in enumerate(results, 1):
#                 st.markdown(f"### 🧾 Resume {i}")
#                 st.write("📧 Sender:", res.get("sender_email", "Unknown"))
#                 st.write("📌 Job Type:", res.get("job_type"))
#                 st.write("📊 Similarity Score:", res.get("similarity_score"))
#                 st.write("🎯 Final Score:", res.get("score"))
#                 st.markdown("---")




    

#     # Option 2: Upload Folder
#     elif menu_option == "📁 Upload Folder":
#         uploaded_files = st.file_uploader("Upload multiple PDF resumes", type="pdf", accept_multiple_files=True)
#         if st.button("📤 Process Uploaded PDFs") and uploaded_files:
#             for f in uploaded_files:
#                 save_path = os.path.join("temp_uploaded", f.name)
#                 os.makedirs("temp_uploaded", exist_ok=True)
#                 with open(save_path, "wb") as out_file:
#                     out_file.write(f.read())
#                 resume_paths.append(save_path)

#     # Option 3: Manual Single Resume Upload
#     elif menu_option == "🧠 Manual Upload":
#         resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")
#         if st.button("🧠 Run Screening") and resume_file:
#             with pdfplumber.open(resume_file) as pdf:
#                 text = "\n".join([page.extract_text() or "" for page in pdf.pages])
#             state = {"resume": text, "jd_text": jd_text}
#             result = graph.invoke(state)
#             st.success("✅ Resume Processed")
#             st.write("📌 Job Type:", result.get('job_type'))
#             st.write("📊 Similarity Score:", result.get('similarity_score'))
#             st.write("🏆 Final Score:", result.get('score'))
#             return  # stop here if manual

#     # Batch processing for Gmail or folder
#     if resume_items:
#         st.info("⏳ Running pipeline on multiple resumes...")
#         results = process_resumes(resume_items, jd_text)

#         for i, res in enumerate(results, 1):
#             st.markdown(f"### 🧾 Resume {i}")
#             st.write("📌 Job Type:", res.get("job_type"))
#             st.write("📊 Similarity Score:", res.get("similarity_score"))
#             st.write("🏆 Final Score:", res.get("score"))

#             # ✅ Feedback Section - must be inside the loop
#             feedback = st.selectbox(
#                 f"Feedback for Resume {i}",
#                 ["Accept", "Reject", "Neutral"],
#                 key=f"feedback_{i}"  # 🔑 ensures each selectbox is uniquely identified
#             )

#             if st.button(f"Submit Feedback {i}"):
#                 send_feedback_email(res.get("sender_email", ""), feedback)
#                 st.success(f"✅ Feedback sent to {res.get('sender_email')}")
#             st.markdown("---")  # Just a visual separator


        
# if __name__ == "__main__":
#     run_streamlit()



from app.utils import extract_text_from_pdf
from app.langgraph_flow import graph  # Make sure graph is defined and imported

def process_resumes(resume_items, jd_text):
    all_results = []

    for i, item in enumerate(resume_items):
        path = item["filepath"]
        sender = item.get("sender_email", "Unknown")
        resume_text = extract_text_from_pdf(path)

        state = {
            "jd_text": jd_text,
            "resume_path": path,
            "resume": resume_text,
            "resume_id": f"resume_{i}",
            "sender_email": sender
        }

        result = graph.invoke(state)
        result["sender_email"] = sender
        all_results.append(result)

    return all_results



def run_streamlit():
    st.set_page_config(page_title="HR Hiring Bot", layout="centered")
    st.title("🤖 HR Hiring Bot")

    menu_option = st.sidebar.radio("Select Mode", ["📩 Gmail Fetch", "📁 Upload Folder", "🧠 Manual Upload"])
    jd_text = st.text_area("📄 Paste Job Description here")

    if not jd_text:
        st.warning("Please enter a job description to proceed.")
        return

    if menu_option == "📩 Gmail Fetch":
        if st.button("📥 Fetch from Gmail"):
            user = os.getenv("GMAIL_USER")
            password = os.getenv("GMAIL_PASS")
            if not user or not password:
                st.error("❌ Gmail credentials not found in .env")
            else:
                resume_items = fetch_resumes_from_gmail(user, password)
                st.success(f"✅ Fetched {len(resume_items)} resumes")

                results = process_resumes(resume_items, jd_text)
                show_results_with_feedback(results)

    elif menu_option == "📁 Upload Folder":
        uploaded_files = st.file_uploader("Upload multiple PDF resumes", type="pdf", accept_multiple_files=True)
        if st.button("📤 Process Uploaded PDFs") and uploaded_files:
            resume_items = []
            os.makedirs("temp_uploaded", exist_ok=True)
            for i, f in enumerate(uploaded_files):
                path = os.path.join("temp_uploaded", f.name)
                with open(path, "wb") as out:
                    out.write(f.read())
                resume_items.append({"filepath": path, "sender_email": "N/A"})

            results = process_resumes(resume_items, jd_text)
            show_results_with_feedback(results)

    elif menu_option == "🧠 Manual Upload":
        resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")
        if st.button("🧠 Run Screening") and resume_file:
            path = os.path.join("manual_uploaded", resume_file.name)
            os.makedirs("manual_uploaded", exist_ok=True)
            with open(path, "wb") as out:
                out.write(resume_file.read())
            resume_text = extract_text_from_pdf(path)
            state = {"jd_text": jd_text, "resume": resume_text}
            result = graph.invoke(state)
            st.success("✅ Resume Processed")
            st.write("📌 Job Type:", result.get("job_type"))
            st.write("📊 Similarity Score:", result.get("similarity_score"))
            st.write("🏆 Final Score:", result.get("score"))






def show_results_with_feedback(results):
    for i, res in enumerate(results, 1):
        st.markdown(f"### 🧾 Resume {i}")
        st.write("📧 Sender:", res.get("sender_email", "Unknown"))
        st.write("📌 Job Type:", res.get("job_type"))
        st.write("📊 Similarity Score:", res.get("similarity_score"))
        st.write("🏆 Final Score:", res.get("score"))

        feedback = st.selectbox(
            f"Feedback for Resume {i}",
            ["Accept", "Reject", "Neutral"],
            key=f"feedback_{i}"
        )

        if st.button(f"Submit Feedback {i}"):
            send_feedback_email(res.get("sender_email", ""), feedback)
            st.success(f"✅ Feedback sent to {res.get('sender_email')}")
        st.markdown("---")


       
if __name__ == "__main__":
    run_streamlit()
