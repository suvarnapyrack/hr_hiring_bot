


















import os
import re
import pdfplumber
import imaplib
import email
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
from app.langgraph_flow import graph
from app.utils import fetch_resumes_from_gmail, extract_text_from_pdf,extract_mobile#, send_feedback_email

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


import os
import re
import streamlit as st
from app.utils import extract_text_from_pdf, fetch_resumes_from_gmail, rank_top_candidates,extract_mobile

# ✅ Display Ranked Candidates
def display_ranked_candidates(processed_resumes):
    top_candidates = rank_top_candidates(processed_resumes)

    if not top_candidates:
        st.warning("⚠️ No suitable candidates found with score > 0.")
        return

    st.subheader("🏆 Top Ranked Candidates")

    for candidate in top_candidates:
        st.markdown(f"""
        ### 🥇 Rank {candidate['rank']}: {candidate['name']}
        - **Email:** {candidate['email']}
        - **Score:** `{candidate['score']}`
        """)


# ✅ Main App
def run_streamlit():
    st.set_page_config(page_title="HR Hiring Bot", layout="centered")
    st.title("🤖 HR Hiring Bot")

    menu_option = st.sidebar.radio("Select Mode", ["📩 Gmail Fetch", "📁 Upload Folder", "🧠 Manual Upload"])
    jd_text = st.text_area("📄 Paste Job Description here")

    if not jd_text:
        st.warning("Please enter a job description to proceed.")
        return

    # 📩 Gmail Fetch Mode
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
                st.success("✅ Resume processing completed!")

                st.subheader("📊 Candidate Scores & Feedback")
                for i, res in enumerate(results, 1):
                    with st.expander(f"📌 Candidate {i}: {res['name']}"):
                        st.markdown(f"- **Email:** {res['email']}")
                        st.markdown(f"- **Mobile:** `{res['mobile']}`")

                        st.markdown(f"- **Score:** `{res['score']}")
                        st.markdown(f"- **Feedback:** `{res['feedback']}`")
                        st.markdown(f"- **Resume:** [Open Resume]({res['resume_path']})")

                # Show ranked top candidates
                display_ranked_candidates(results)  # Pass already scored resumes


    # 📁 Upload Folder Mode
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
            st.success("✅ Resume processing completed!")

            st.subheader("📊 Candidate Scores & Feedback")
            for i, res in enumerate(results, 1):
                with st.expander(f"📌 Candidate {i}: {res['name']}"):
                    st.markdown(f"- **Email:** {res['email']}")
                    st.markdown(f"- **Score:** `{res['score']}`")
                    st.markdown(f"- **Feedback:** `{res['feedback']}`")
                    st.markdown(f"- **Resume:** [Open Resume]({res['resume_path']})")

            # Show top ranked
            display_ranked_candidates(jd_text, resume_items)

    # 🧠 Manual Upload
    elif menu_option == "🧠 Manual Upload":
        resume_file = st.file_uploader("📎 Upload Resume (PDF Only)", type="pdf")
        if st.button("🧠 Run Screening") and resume_file:
            path = os.path.join("manual_uploaded", resume_file.name)
            os.makedirs("manual_uploaded", exist_ok=True)
            with open(path, "wb") as out:
                out.write(resume_file.read())

            resume_text = extract_text_from_pdf(path)
            state = {"jd_text": jd_text, "resume": resume_text}
            from app.graph import graph  # Assuming LangGraph is used
            result = graph.invoke(state)

            st.success("✅ Resume Processed")
            st.markdown(f"📌 **Job Type:** `{result.get('job_type')}`")
            st.markdown(f"🏆 **Final Score:** `{result.get('score')}`")

# ✅ Run the app
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
