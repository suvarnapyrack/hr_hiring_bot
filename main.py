


















import os
import re
import pdfplumber
import imaplib
import email
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.langgraph_flow import graph
from app.utils import fetch_resumes_from_gmail, extract_text_from_pdf,extract_mobile #, send_feedback_email

load_dotenv()








    




from app.utils import extract_text_from_pdf
from app.langgraph_flow import graph  # Make sure graph is defined and imported

from app.utils import score_resume
def process_resumes(resume_items, jd_text):
    all_results = []

    for i, item in enumerate(resume_items):
        path = item["filepath"]
        sender = item.get("sender_email", "Unknown")
        resume_text = extract_text_from_pdf(path)

        state = {
            "jd_text": jd_text,
            "resume": resume_text,
            "resume_text": resume_text,  # ✅ ADD this line for ranking
            "resume_path": path,
            "resume_id": f"resume_{i}",
            "sender_email": sender,
            "mobile": extract_mobile(resume_text)  # Extract mobile number from resume text
        }

        # Step 1: Run LangGraph
        state = graph.invoke(state)

        # Step 2: Apply scoring
        state = score_resume(state)

        # Step 3: Skip resumes with low experience
        if state.get("experience_filtered"):
            continue

        # Step 4: Collect results
        name = state.get("name", f"Candidate {i+1}")
        email = state.get("email", sender)
        score = state.get("score", 0)
        feedback = "Accept" if score >= 6.5 else "Reject"

        # ✅ Append all required fields
        all_results.append({
            "name": name,
            "email": email,
            "score": score,
            "feedback": feedback,
            "mobile": state.get("mobile", "Not available"),
            "resume_path": path,
            "resume_text": resume_text,     # ✅ needed for ranking
            "resume_id": f"resume_{i}",     # ✅ optional, used in utils
        })

    return all_results


# import os
# import re
# import streamlit as st
# from app.utils import extract_text_from_pdf, fetch_resumes_from_gmail, rank_top_candidates,extract_mobile

# # ✅ Display Ranked Candidates
# def display_ranked_candidates(processed_resumes):
#     top_candidates = rank_top_candidates(processed_resumes)

#     if not top_candidates:
#         st.warning("⚠️ No suitable candidates found with score > 0.")
#         return

#     st.subheader("🏆 Top Ranked Candidates")

#     for candidate in top_candidates:
#         st.markdown(f"""
#         ### 🥇 Rank {candidate['rank']}: {candidate['name']}
#         - **Email:** {candidate['email']}
#         - **Score:** {candidate['score']}
#         """)


# # ✅ Main App
# def run_streamlit():
#     st.set_page_config(page_title="HR Hiring Bot", layout="centered")
#     st.title("🤖 HR Hiring Bot")

#     menu_option = st.sidebar.radio("Select Mode", ["📩 Gmail Fetch", "📁 Upload Folder", "🧠 Manual Upload"])
#     jd_text = st.text_area("📄 Paste Job Description here")

#     if not jd_text:
#         st.warning("Please enter a job description to proceed.")
#         return

#     # 📩 Gmail Fetch Mode
#     if menu_option == "📩 Gmail Fetch":
#         if st.button("📥 Fetch from Gmail"):
#             user = os.getenv("GMAIL_USER")
#             password = os.getenv("GMAIL_PASS")

#             if not user or not password:
#                 st.error("❌ Gmail credentials not found in .env")
#             else:
#                 resume_items = fetch_resumes_from_gmail(user, password)
#                 st.success(f"✅ Fetched {len(resume_items)} resumes")

#                 results = process_resumes(resume_items, jd_text)
#                 st.success("✅ Resume processing completed!")

#                 st.subheader("📊 Candidate Scores & Feedback")
#                 for i, res in enumerate(results, 1):
#                     with st.expander(f"📌 Candidate {i}: {res['name']}"):
#                         st.markdown(f"- **Email:** {res['email']}")
#                         st.markdown(f"- **Mobile:** {res['mobile']}")

#                         st.markdown(f"- **Score:** {res['score']}")
#                         st.markdown(f"- **Feedback:** `{res['feedback']}`")
#                         st.markdown(f"- **Resume:** [Open Resume]({res['resume_path']})")

#                 # Show ranked top candidates
#                 display_ranked_candidates(results)  # Pass already scored resumes


#     # 📁 Upload Folder Mode
#     elif menu_option == "📁 Upload Folder":
#         uploaded_files = st.file_uploader("Upload multiple PDF resumes", type="pdf", accept_multiple_files=True)
#         if st.button("📤 Process Uploaded PDFs") and uploaded_files:
#             resume_items = []
#             os.makedirs("temp_uploaded", exist_ok=True)
#             for i, f in enumerate(uploaded_files):
#                 path = os.path.join("temp_uploaded", f.name)
#                 with open(path, "wb") as out:
#                     out.write(f.read())
#                 resume_items.append({"filepath": path, "sender_email": "N/A"})

#             results = process_resumes(resume_items, jd_text)
#             st.success("✅ Resume processing completed!")

#             st.subheader("📊 Candidate Scores & Feedback")
#             for i, res in enumerate(results, 1):
#                 with st.expander(f"📌 Candidate {i}: {res['name']}"):
#                     st.markdown(f"- **Email:** {res['email']}")
#                     st.markdown(f"- **Score:** {res['score']}")
#                     st.markdown(f"- **Feedback:** {res['feedback']}")
#                     st.markdown(f"- **Resume:** [Open Resume]({res['resume_path']})")

#             # Show top ranked
#             display_ranked_candidates(jd_text, resume_items)

#     # 🧠 Manual Upload
#     elif menu_option == "🧠 Manual Upload":
#         resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")
#         if st.button("🧠 Run Screening") and resume_file:
#             path = os.path.join("manual_uploaded", resume_file.name)
#             os.makedirs("manual_uploaded", exist_ok=True)
#             with open(path, "wb") as out:
#                 out.write(resume_file.read())

#             resume_text = extract_text_from_pdf(path)
#             state = {"jd_text": jd_text, "resume": resume_text}
#             from app.graph import graph  # Assuming LangGraph is used
#             result = graph.invoke(state)

#             st.success("✅ Resume Processed")
#             st.markdown(f"📌 **Job Type:** {result.get('job_type')}")
#             st.markdown(f"🏆 **Final Score:** {result.get('score')}")

# # ✅ Run the app
# if __name__ == "__main__":
#     run_streamlit()













import os
import streamlit as st
from app.utils import (
    extract_text_from_pdf,            # PDF text extractor (your existing function)
    fetch_resumes_from_gmail,        # should return list of resume items (e.g. dicts with filepath or bytes)
    # process_resumes,                 # your existing pipeline that scores resumes vs jd_text
    rank_top_candidates              # optional ranking function (fallback)
)

# -----------------------
# UI / CSS
# -----------------------
def load_custom_css():
    st.markdown(
        """
        <style>
        /* page background */
        .stApp {
            background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
            font-family: 'Inter', sans-serif;
        }

        /* header */
        h1 { color: #05386B; font-weight: 800; }

        /* sidebar - light */
        [data-testid="stSidebar"] {
            background: #fbfdff;
            border-right: 1px solid #e6eef6;
        }

        /* buttons */
        .stButton>button {
            background: linear-gradient(90deg,#0077b6,#00b4d8);
            color: white;
            border-radius: 10px;
            padding: 8px 14px;
            font-weight: 600;
        }
        .stButton>button:hover { transform: translateY(-2px); }

        /* candidate cards */
        .candidate-card {
            background: #ffffff;
            padding: 14px;
            border-radius: 12px;
            box-shadow: 0 6px 18px rgba(3, 23, 55, 0.06);
            margin-bottom: 12px;
        }

        /* small helper */
        .muted { color: #6b7280; font-size: 13px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


# -----------------------
# Helper: Display results (expander style)
# -----------------------
def display_ranked_candidates(processed_resumes):
    """
    Accepts a list of processed resume dicts. Each dict ideally contains:
      - name, email, mobile, score, feedback, resume_path
    If processed_resumes is not ranked, attempt to call rank_top_candidates() to compute ordering.
    """
    if not processed_resumes:
        st.warning("⚠️ No candidates to display.")
        return

    # If items don't have a 'rank' key, attempt to rank them using rank_top_candidates
    need_rank = not all("rank" in r for r in processed_resumes)
    if need_rank:
        try:
            top = rank_top_candidates(processed_resumes)
        except Exception:
            # fallback: simple sort by 'score' if present
            top = sorted(processed_resumes, key=lambda x: x.get("score", 0), reverse=True)
        processed_resumes = top

    st.subheader("🏆 Top Ranked Candidates")
    for i, res in enumerate(processed_resumes, 1):
        with st.expander(f"📌 Candidate {i}: {res.get('name','Unknown')}"):
            st.markdown(f"📧 **Email:** {res.get('email','N/A')}")
            st.markdown(f"📱 **Mobile:** {res.get('mobile','N/A')}")
            st.markdown(f"💯 **Score:** {res.get('score','N/A')}")
            st.markdown(f"📝 **Feedback:** `{res.get('feedback','No feedback')}`")
            resume_link = res.get("resume_path") or res.get("filepath") or "#"
            st.markdown(f"📄 **Resume:** [Open Resume]({resume_link})")

# -----------------------
# Main app
# -----------------------
def run_streamlit():
    load_custom_css()
    st.set_page_config(page_title="HR Hiring Bot", layout="wide")

    # initialize session state
    if "resume_items" not in st.session_state:
        st.session_state["resume_items"] = []   # list of resume dicts or {"filepath":...}
    if "jd_text" not in st.session_state:
        st.session_state["jd_text"] = ""
    if "jd_submitted" not in st.session_state:
        st.session_state["jd_submitted"] = False
    if "results" not in st.session_state:
        st.session_state["results"] = []

    # top/header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("<h1>🤖 HR Hiring Bot</h1>", unsafe_allow_html=True)
        st.markdown("<div class='muted'>Fetch resumes from Gmail / folder / manual upload → Submit JD → Rank candidates</div>", unsafe_allow_html=True)
    with col2:
        st.markdown("")  # reserved

    # Sidebar: choose source
    source = st.sidebar.radio("🔎 Select Source", ["Gmail", "Upload Folder", "Manual Upload", "View Results"])

    # -------------------------
    # Job Description area (main)
    # -------------------------
    st.markdown("## 📄 Job Description")
    jd_col1, jd_col2 = st.columns([4,1])
    with jd_col1:
        jd_text_input = st.text_area("Paste Job Description here (or upload JD file below)", height=180, value=st.session_state["jd_text"])
        jd_file = st.file_uploader("Optional: Upload JD (txt, pdf)", type=["txt","pdf"], help="If you upload a JD file it will replace the text area.")
    with jd_col2:
        if st.button("✅ Submit Job Description"):
            # if file uploaded, extract text (if pdf use extract_text_from_pdf)
            final_jd_text = ""
            if jd_file is not None:
                if jd_file.name.lower().endswith(".pdf"):
                    # save temporarily and call your extractor
                    tmp_dir = "temp_jd"
                    os.makedirs(tmp_dir, exist_ok=True)
                    tmp_path = os.path.join(tmp_dir, jd_file.name)
                    with open(tmp_path, "wb") as f:
                        f.write(jd_file.getbuffer())
                    try:
                        final_jd_text = extract_text_from_pdf(tmp_path)
                    except Exception as e:
                        st.error("Error extracting text from JD PDF: " + str(e))
                        final_jd_text = ""
                else:
                    try:
                        final_jd_text = jd_file.read().decode("utf-8")
                    except Exception:
                        final_jd_text = ""
            else:
                final_jd_text = jd_text_input

            if final_jd_text and final_jd_text.strip():
                st.session_state["jd_text"] = final_jd_text
                st.session_state["jd_submitted"] = True
                st.success("✅ Job Description submitted. You can now rank resumes.")
            else:
                st.warning("⚠️ Please paste or upload a valid Job Description before submitting.")

    # Show current JD status
    if st.session_state["jd_submitted"]:
        st.info("✅ JD submitted. Ready for ranking.")
    else:
        st.info("ℹ️ JD not submitted yet — you can still fetch resumes and save them, then submit JD when ready.")

    st.markdown("---")

    # -------------------------
    # Source-specific UI
    # -------------------------
    if source == "Gmail":
        st.subheader("📩 Fetch from Gmail")
        with st.form("gmail_form", clear_on_submit=False):
            gmail_user = st.text_input("Gmail Username (or leave empty to use env)")
            gmail_pass = st.text_input("Gmail App Password / OAuth token", type="password")
            submitted = st.form_submit_button("📥 Fetch from Gmail")
            if submitted:
                user = gmail_user.strip() or os.getenv("GMAIL_USER")
                pwd = gmail_pass.strip() or os.getenv("GMAIL_PASS")
                if not user or not pwd:
                    st.error("❌ Gmail credentials not provided (env or field).")
                else:
                    with st.spinner("📡 Fetching resumes from Gmail..."):
                        try:
                            items = fetch_resumes_from_gmail(user, pwd)
                            # expected items: list of dicts (e.g. {'filepath': '/path/...', ...})
                            st.session_state["resume_items"] = items or []
                            st.success(f"✅ Fetched {len(st.session_state['resume_items'])} resumes from Gmail.")
                        except Exception as e:
                            st.error("Error fetching from Gmail: " + str(e))

        # show small preview of fetched files
        if st.session_state["resume_items"]:
            st.markdown("**Fetched resumes (preview):**")
            for r in st.session_state["resume_items"][:10]:
                st.write("- " + (r.get("sender_email") or r.get("filename") or r.get("filepath", "Unknown")))

    elif source == "Upload Folder":
        st.subheader("📁 Upload Folder (multiple resumes)")
        st.markdown("Upload multiple resumes (pdf / docx) — they will be saved temporarily and listed.")
        uploaded_files = st.file_uploader("Upload multiple resumes", accept_multiple_files=True, type=["pdf","docx","doc"])
        if st.button("📂 Save uploaded files"):
            if not uploaded_files:
                st.warning("Please upload one or more resume files.")
            else:
                os.makedirs("temp_uploaded", exist_ok=True)
                saved = []
                for f in uploaded_files:
                    path = os.path.join("temp_uploaded", f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved.append({"filepath": path, "sender_email": "N/A", "filename": f.name})
                st.session_state["resume_items"] = saved
                st.success(f"✅ Saved {len(saved)} files to temp_uploaded.")
        if st.session_state["resume_items"]:
            st.markdown("**Recently uploaded resumes:**")
            for r in st.session_state["resume_items"]:
                st.write("- " + (r.get("filename") or r.get("filepath")))

    elif source == "Manual Upload":
        st.subheader("📤 Manual Upload (single or multiple resumes)")
        uploaded_files = st.file_uploader("Upload resume(s)", accept_multiple_files=True, type=["pdf","docx","doc"])
        if st.button("📥 Add to workspace"):
            if not uploaded_files:
                st.warning("Please upload resume(s).")
            else:
                os.makedirs("temp_uploaded", exist_ok=True)
                added = st.session_state.get("resume_items", [])
                for f in uploaded_files:
                    path = os.path.join("temp_uploaded", f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    added.append({"filepath": path, "sender_email": "Manual Upload", "filename": f.name})
                st.session_state["resume_items"] = added
                st.success(f"✅ Added {len(uploaded_files)} resumes to workspace.")

        if st.session_state["resume_items"]:
            st.markdown("**Current workspace resumes (click View Results to see ranked output after submitting JD):**")
            for r in st.session_state["resume_items"]:
                st.write("- " + (r.get("filename") or r.get("filepath")))

    elif source == "View Results":
        st.subheader("🧾 Workspace & Results")
        st.markdown("You can fetch/add resumes from any source (Gmail / Upload folder / Manual). They are stored temporarily in the workspace. Then submit a JD and click **Rank & Process** below to score them.")

        st.markdown("**Workspace resumes:**")
        if not st.session_state["resume_items"]:
            st.info("No resumes in workspace yet. Use Gmail / Upload / Manual to add resumes.")
        else:
            for r in st.session_state["resume_items"]:
                st.write("- " + (r.get("filename") or r.get("filepath") or r.get("sender_email", "resume")))

        colA, colB = st.columns(2)
        with colA:
            if st.button("⚙️ Rank & Process resumes (use submitted JD)"):
                if not st.session_state["resume_items"]:
                    st.warning("Please add/fetch resumes first.")
                elif not st.session_state["jd_submitted"]:
                    st.warning("Please submit the Job Description first (top-right).")
                else:
                    with st.spinner("⚙️ Processing & scoring resumes..."):
                        try:
                            # process_resumes should return a list of result dicts
                            results = process_resumes(st.session_state["resume_items"], st.session_state["jd_text"])
                            st.session_state["results"] = results or []
                            st.success("✅ Resume processing completed!")
                        except Exception as e:
                            st.error("Error during resume processing: " + str(e))
        with colB:
            if st.button("🧹 Clear workspace"):
                st.session_state["resume_items"] = []
                st.session_state["results"] = []
                st.success("Workspace cleared.")

        # show processed results if present
        if st.session_state["results"]:
            display_ranked_candidates(st.session_state["results"])
        else:
            st.info("No processed results yet. After ranking, results will appear here.")

    # small footer
    # st.markdown("---")
    # st.markdown("💡 Tip: You can fetch resumes first (Gmail / Upload), submit JD anytime, then use **View Results → Rank & Process** to get the ranked candidates.")

# run
if __name__ == "__main__":
    run_streamlit()




import streamlit as st
import os
import pdfplumber


from dotenv import load_dotenv
load_dotenv()

import os
import streamlit as st
from email.mime.text import MIMEText
import smtplib


import re


def extract_email(raw_email):
    match = re.search(r'<(.+?)>', raw_email)
    return match.group(1).strip() if match else raw_email.strip()










































































# from app.utils import send_feedback_email  # ✅ make sure this is your HTML version

# def send_bulk_feedback_emails(email_feedback_list):
#     print(f"✅ Reached send_bulk_feedback_emails : {email_feedback_list}")

#     for to_email, feedback_text in email_feedback_list:
#         try:
#             send_feedback_email(to_email, feedback_text)  # ✅ this uses HTML email now
#         except Exception as e:
#             st.error(f"❌ Failed to send to {to_email}: {e}")


# def collect_feedback_and_send(results):
#     st.title("🤖 HR Bot – Auto Feedback & Mailing")

#     email_feedback_list = []

#     for i, res in enumerate(results):
#         raw_email = res.get("sender_email", "")
#         email = extract_email(raw_email)
#         score = res.get("score", 0)
#         job_type = res.get("job_type", "Unknown")

#         feedback ="Accept" if score >= 3 else "Reject"


#         with st.expander(f"📄 Resume {i+1}: {job_type}"):
#             st.write(f"📧 Email: {email}")
#             st.write(f"📌 Job Type: {job_type}")
            
#             st.write(f"🏆 Final Score: {score}")
#             st.write(f"🗣️ Auto Feedback: `{feedback}`")

#         email_feedback_list.append((email, feedback))
#         print(f"🔔 Prepared feedback for: {email} - {feedback}")
#     print("🔔 Outside the loop...")
#     send_bulk_feedback_emails(email_feedback_list)
        


# def extract_email(raw_email):
#     match = re.search(r'<(.+?)>', raw_email)
#     return match.group(1).strip() if match else raw_email.strip()

# def collect_feedback(results):
#     feedback_list = []
#     st.title("🧠 HR Feedback Collection")

#     for i, res in enumerate(results, 1):
#         st.markdown(f"### 🧾 Resume {i}")

#         raw_email = res.get("sender_email", "")
#         email = extract_email(raw_email)
#         job_type = res.get("job_type", "Unknown")
#         sim_score = res.get("similarity_score", "N/A")
#         final_score = res.get("score", "N/A")

#         st.write(f"📧 Email: {email}")
#         st.write(f"💼 Job Type: {job_type}")
#         st.write(f"📊 Similarity Score: {sim_score}")
#         st.write(f"🏆 Final Score: {final_score}")

#         with st.form(f"form_{i}"):
#             feedback = st.selectbox("Select Feedback", ["Accept", "Reject"], key=f"fb_{i}")
#             submitted = st.form_submit_button("Submit Feedback")
#             if submitted:
#                 feedback_list.append((email, feedback))
#                 st.success(f"Feedback '{feedback}' submitted for {email}")

        
#         st.markdown("---")

#     return feedback_list


# def send_bulk_feedback_emails(email_feedback_list):
#     print(f"✅ Reached send_bulk_feedback_emails : {email_feedback_list}")
#     from_email = os.getenv("GMAIL_USER")
#     app_password = os.getenv("GMAIL_PASS")

#     if not from_email or not app_password:
#         print("❌ Gmail credentials missing")
#         return

#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(from_email, app_password)
#             for to_email, feedback_text in email_feedback_list:
#                 subject = "Feedback on Your Resume Submission"
#                 body = f"Dear Candidate,\n\nThank you for your application.\nFeedback: {feedback_text}\n\nBest regards,\nHR Bot"

#                 msg = MIMEText(body)
#                 msg["Subject"] = subject
#                 msg["From"] = from_email
#                 msg["To"] = to_email

#                 try:
#                     server.sendmail(from_email, to_email, msg.as_string())
#                     print(f"✅ Email sent to {to_email}")
#                 except Exception as e:
#                     print(f"❌ Failed to send email to {to_email}: {e}")
#     except Exception as e:
#         print("❌ SMTP connection error:", str(e))

# # def show_results_with_feedback(results):
#     print(f"🔍 FINAL RESULTS TO DISPLAY: {results}")
#     for i, res in enumerate(results, 1):
#         st.markdown(f"### 🧾 Resume {i}")
#         sender_email = res.get("sender_email", "")
#         st.write("📧 Sender:", sender_email)
#         st.write("📌 Job Type:", res.get("job_type"))
#         st.write("📊 Similarity Score:", res.get("similarity_score"))
#         st.write("🏆 Final Score:", res.get("score"))

#         with st.form(key=f"feedback_form_{i}"):
#             feedback = st.selectbox(
#                 f"Feedback for Resume {i}",
#                 ["Accept", "Reject", "Neutral"]
#             )
#             submit = st.form_submit_button("Submit Feedback")
#             print(f"🔔 Preparing to send feedback to: {sender_email, feedback}")

#             if submit:
#                 print(f"🔔 Preparing to send feedback to: {sender_email}")
#                 if sender_email:
#                     send_feedback_email(sender_email, feedback)
#                     st.success(f"✅ Feedback sent to {sender_email}")
#                 else:
#                     st.error("❌ No sender email found.")
                    
#         st.markdown("---")




# if __name__ == "__main__":
#     run_streamlit()
