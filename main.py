# # import streamlit as st
# # from app.ui import show_ui
# # from app.langgraph_flow import build_langgraph_flow

# # graph = build_langgraph_flow()

# # def run():
# #     jd_text, resume_file = show_ui()
# #     if st.button("🧠 Run Screening") and jd_text and resume_file:
# #         state = {"jd_text": jd_text, "resume": resume_file}
# #         result = graph.invoke(state)
# #         st.success("✅ Resume Processed")
# #         st.write("📌 Job Type:", result['job_type'])
# #         st.write("📊 Similarity Score:", result['similarity_score'])
# #         st.write("🏆 Final Score:", result['score'])

# # if __name__ == "__main__":
# #     run()



# # import streamlit as st
# # import pdfplumber
# # from app.ui import show_ui
# # from app.langgraph_flow import build_langgraph_flow

# # graph = build_langgraph_flow()

# # def run():
# #     jd_text, resume_file = show_ui()

# #     if st.button("🧠 Run Screening") and jd_text and resume_file:
# #         # ✅ Extract resume text from uploaded PDF
# #         with pdfplumber.open(resume_file) as pdf:
# #             text = "\n".join([page.extract_text() or "" for page in pdf.pages])

# #         # ✅ Ensure state has expected keys
# #         state = {
# #         "resume": text,
# #         "jd_text": jd_text   # ✅ Use this key to match utils.py
# #     }

# #         result = graph.invoke(state)
# #         st.success("✅ Resume Processed")
# #         st.write("📌 Job Type:", result.get('job_type'))
# #         st.write("📊 Similarity Score:", result.get('similarity_score'))
# #         st.write("🏆 Final Score:", result.get('score'))

# # if __name__ == "__main__":
# #     run()


# # from app.resume_fetch import fetch_resumes_from_gmail


# # def run():
# #     # ✅ Fetch resumes from Gmail first
# #     fetch_resumes_from_gmail(
# #         os.getenv("GMAIL_USER"),
# #         os.getenv("GMAIL_PASSWORD"),
# #         download_dir="resumes"
# #     )

# #     jd_text, resume_file = show_ui()

# #     if st.button("🧠 Run Screening") and jd_text and resume_file:
# #         ...







# import os
# import streamlit as st
# import pdfplumber
# from dotenv import load_dotenv

# # ✅ Load environment variables
# load_dotenv()

# # ✅ Import local modules
# from app.ui import show_ui
# from app.langgraph_flow import build_langgraph_flow
# from app.resume_fetch import fetch_resumes_from_gmail

# # ✅ Compile the LangGraph
# graph = build_langgraph_flow()

# def run():
#     st.title("🤖 HR Hiring Bot")

#     # ✅ Step 1: Fetch resumes from Gmail
#     if st.button("📩 Fetch Resumes from Gmail"):
#         user = os.getenv("GMAIL_USER")
#         password = os.getenv("GMAIL_PASSWORD")

#         if not user or not password:
#             st.error("❌ Gmail credentials not found in .env")
#         else:
#             fetch_resumes_from_gmail(user, password)
#             st.success("✅ Fetched resumes from Gmail")

#     # ✅ Step 2: Run screening manually (after Gmail fetch or upload)
#     jd_text, resume_file = show_ui()

#     if st.button("🧠 Run Screening") and jd_text and resume_file:
#         with pdfplumber.open(resume_file) as pdf:
#             text = "\n".join([page.extract_text() or "" for page in pdf.pages])

#         state = {
#             "resume": text,
#             "jd_text": jd_text
#         }

#         result = graph.invoke(state)
#         st.success("✅ Resume Processed")
#         st.write("📌 Job Type:", result.get('job_type'))
#         st.write("📊 Similarity Score:", result.get('similarity_score'))
#         st.write("🏆 Final Score:", result.get('score'))

# if __name__ == "__main__":
#     run()







# def run_pipeline_on_resumes(jd_text):
#     GMAIL_USER = os.getenv("GMAIL_USER")
#     GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

#     resume_paths = fetch_resumes_from_gmail(GMAIL_USER, GMAIL_APP_PASSWORD)
#     results = []
#     for path in resume_paths:
#         resume_text = extract_text_from_pdf(path)
#         state = {
#             "resume": resume_text,
#             "jd_text": jd_text,
#             "file_name": os.path.basename(path)
#         }
#         result = graph.invoke(state)
#         results.append(result)
#     return results




# import os
# import re
# import pdfplumber
# import imaplib
# import email
# from app.langgraph_flow import graph
# from app.utils import fetch_resumes_from_gmail,extract_text_from_pdf
 
# import streamlit as st
# from datetime import datetime, timedelta
# from dotenv import load_dotenv
# from langchain_core.prompts import PromptTemplate
# from langchain_groq import ChatGroq
# from langgraph.graph import StateGraph, END

# # -------------------- Streamlit UI -------------------- #
# def run_streamlit():
#     st.title("🤖 HR Hiring Bot")

#     # Step 1: Gmail Fetch Button
#     if st.button("📩 Fetch Resumes from Gmail"):
#         user = os.getenv("GMAIL_USER")
#         password = os.getenv("GMAIL_PASS")

#         if not user or not password:
#             st.error("❌ Gmail credentials not found in .env")
#         else:
#             resume = fetch_resumes_from_gmail(user, password)
#             st.success(f"✅ Fetched resumes from Gmail: {resume}")


#     # Step 2: Manual JD + Resume Screening
#     jd_text = st.text_area("📄 Job Description")
#     resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")

#     if st.button("🧠 Run Screening") and jd_text and resume_file:
#         with pdfplumber.open(resume_file) as pdf:
#             text = "\n".join([page.extract_text() or "" for page in pdf.pages])

#         state = {
#             "resume": text,
#             "jd_text": jd_text
#         }

#         result = graph.invoke(state)
#         st.success("✅ Resume Processed")
#         st.write("📌 Job Type:", result.get('job_type'))
#         st.write("📊 Similarity Score:", result.get('similarity_score'))
#         st.write("🏆 Final Score:", result.get('score'))

# # -------------------- CLI Pipeline Runner -------------------- #
# def run_pipeline_on_resumes(jd_text):
#     GMAIL_USER = os.getenv("GMAIL_USER")
#     GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

#     resume_paths = fetch_resumes_from_gmail(GMAIL_USER, GMAIL_APP_PASSWORD)
#     results = []
#     for path in resume_paths:
#         resume_text = extract_text_from_pdf(path)
#         state = {
#             "resume": resume_text,
#             "jd_text": jd_text,
#             "file_name": os.path.basename(path)
#         }
#         result = graph.invoke(state)
#         results.append(result)
#     return results

# # -------------------- Main Entry -------------------- #
# if __name__ == "__main__":
#     run_streamlit()






import os
import re
import pdfplumber
import imaplib
import email
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.langgraph_flow import graph
from app.utils import fetch_resumes_from_gmail, extract_text_from_pdf

load_dotenv()

# -------------------- Common Resume Processing -------------------- #
def process_resumes(resume_paths, jd_text):
    results = []
    for path in resume_paths:
        resume_text = extract_text_from_pdf(path)
        state = {
            "resume": resume_text,
            "jd_text": jd_text,
            "file_name": os.path.basename(path)
        }
        result = graph.invoke(state)
        results.append(result)
    return results

# -------------------- Streamlit UI -------------------- #
def run_streamlit():
    st.set_page_config(page_title="HR Hiring Bot", layout="centered")
    st.title("🤖 HR Hiring Bot")

    menu_option = st.sidebar.radio("Select Mode", ["📩 Gmail Fetch", "📁 Upload Folder", "🧠 Manual Upload"])

    jd_text = st.text_area("📄 Paste Job Description here")

    if not jd_text:
        st.warning("Please enter a job description to proceed.")
        return

    resume_paths = []

    # Option 1: Gmail Fetch
    if menu_option == "📩 Gmail Fetch":
        if st.button("📥 Fetch from Gmail"):
            user = os.getenv("GMAIL_USER")
            password = os.getenv("GMAIL_PASS")
            if not user or not password:
                st.error("❌ Gmail credentials not found in .env")
            else:
                    resume_paths = fetch_resumes_from_gmail(user, password)
        if resume_paths:
            st.success(f"✅ Fetched {len(resume_paths)} resumes")
            
            st.info("⏳ Analyzing fetched resumes...")
            results = process_resumes(resume_paths, jd_text)

            for i, res in enumerate(results, 1):
                st.markdown(f"### 🧾 Resume {i}: {res.get('file_name', 'Unknown')}")
                st.write("📌 Job Type:", res.get('job_type'))
                st.write("📊 Similarity Score:", res.get('similarity_score'))
                st.write("🎯 Final Score:", res.get('score'))
                st.markdown("---")
        else:
            st.warning("❌ No resumes found in Gmail.")


    # Option 2: Upload Folder
    elif menu_option == "📁 Upload Folder":
        uploaded_files = st.file_uploader("Upload multiple PDF resumes", type="pdf", accept_multiple_files=True)
        if st.button("📤 Process Uploaded PDFs") and uploaded_files:
            for f in uploaded_files:
                save_path = os.path.join("temp_uploaded", f.name)
                os.makedirs("temp_uploaded", exist_ok=True)
                with open(save_path, "wb") as out_file:
                    out_file.write(f.read())
                resume_paths.append(save_path)

    # Option 3: Manual Single Resume Upload
    elif menu_option == "🧠 Manual Upload":
        resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")
        if st.button("🧠 Run Screening") and resume_file:
            with pdfplumber.open(resume_file) as pdf:
                text = "\n".join([page.extract_text() or "" for page in pdf.pages])
            state = {"resume": text, "jd_text": jd_text}
            result = graph.invoke(state)
            st.success("✅ Resume Processed")
            st.write("📌 Job Type:", result.get('job_type'))
            st.write("📊 Similarity Score:", result.get('similarity_score'))
            st.write("🏆 Final Score:", result.get('score'))
            return  # stop here if manual

    # Batch processing for Gmail or folder
    if resume_paths:
        st.info("⏳ Running pipeline on multiple resumes...")
        results = process_resumes(resume_paths, jd_text)

        for i, res in enumerate(results, 1):
            st.markdown(f"### 🧾 Resume {i}: {res.get('file_name', 'Unknown')}")
            st.write("📌 Job Type:", res.get('job_type'))
            st.write("📊 Similarity Score:", res.get('similarity_score'))
            st.write("🎯 Final Score:", res.get('score'))
            st.markdown("---")

# -------------------- Main Entry -------------------- #
if __name__ == "__main__":
    run_streamlit()

