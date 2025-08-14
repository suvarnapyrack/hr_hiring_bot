
import os
import re
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json

# Import your updated functions
#from app import create_resume_processing_graph
from app.utils import  rank_top_candidates, fetch_from_gmail,fetch_from_drive
from app.utils import extract_text_from_pdf, parse_resume
from app.langgraph_flow import graph

load_dotenv()



def process_resumes(resume_items, jd_text, source_type="manual"):
    """
    Process multiple resumes using the LangGraph pipeline
    """
    all_results = []

    for i, item in enumerate(resume_items):
        # Handle different item structures
        if isinstance(item, dict):
            path = item.get("filepath") or item.get("file_path")
            sender = item.get("sender_email", "Unknown")
            filename = item.get("filename", f"resume_{i}")
        else:
            path = item
            sender = "Unknown"
            filename = f"resume_{i}"

        if not path or not os.path.exists(path):
            st.warning(f"⚠️ File not found: {path}")
            continue

        try:
            # ✅ STEP 1: Extract resume text first
            resume_text = ""
            if path.lower().endswith('.pdf'):
                resume_text = extract_text_from_pdf(path)  # Make sure this function exists in utils.py
            elif path.lower().endswith(('.docx', '.doc')):
            #     resume_text = extract_text_from_docx(path)  # Make sure this function exists in utils.py
            # elif path.lower().endswith('.txt'):
                with open(path, 'r', encoding='utf-8') as f:
                    resume_text = f.read()
            
            if not resume_text.strip():
                st.warning(f"⚠️ Could not extract text from: {filename}")
                continue

            # ✅ STEP 2: Create initial state with extracted text
            initial_state = {
                "source_type": source_type,
                "jd_text": jd_text,
                "resume": path,
                "resume_text": resume_text,  # Now we have the actual text
                "mobile": "",
                "email": "",
                "name": "",
                "similarity_score": 0,
                "llm_score": 0,
                "embedding_score": 0,
                "job_type": "",
                "analysis": {},
                "score": 0,
                "experience_filtered": False,
                "rank": 0
            }

            # ✅ STEP 3: Parse the resume to extract name, email, mobile
            parsed_state = parse_resume(initial_state)
            print("=" * 50)
            print(f"--parsed_state : {parsed_state}")
            print("=" * 50)
    

            # Debug: Check if parsing worked
            st.info(f"🔍 Parsing results for {filename}:")
            st.info(f"   - Name: {parsed_state.get('name', 'Not found')}")
            st.info(f"   - Email: {parsed_state.get('email', 'Not found')}")
            st.info(f"   - Mobile: {parsed_state.get('mobile', 'Not found')}")

            # ✅ STEP 4: Run the LangGraph pipeline
            result_state = graph.invoke(parsed_state)

            print("=" * 50)
            print(f"LangGraph state : {result_state}")
            print("=" * 50)

            # ✅ STEP 5: Extract results with proper fallbacks
            name = result_state.get("name") #or f"Candidate_{i+1}"
            email = result_state.get("email") #or sender
            mobile = result_state.get("mobile") #or "Not available"

            print("=" * 50)
            print(f"Extract results : {name},{email},{mobile}")
            print("=" * 50)

            # Determine feedback based on score
            score = result_state.get("score", 0)
            feedback = "Accept" if score >= 6.5 else "Reject"

            if result_state.get("experience_filtered", False):
                feedback = "Rejected (Experience)"
                st.info(f"📋 {name}: Filtered out due to insufficient experience")

            analysis = result_state.get("analysis", {})

            # Collect results
            result_data = {
                "name": name,
                "email": email,
                "score": score,
                "feedback": feedback,
                "mobile": mobile,
                "resume_path": path,
                "filename": filename,
                "job_type": result_state.get("job_type", "Unknown"),
                "skills": analysis.get("skills", []),
                "education": analysis.get("education", "Unknown"),
                "experience": analysis.get("experience", "0"),
                "similarity_score": result_state.get("similarity_score", 0),
                "llm_score": result_state.get("llm_score", 0),
                "embedding_score": result_state.get("embedding_score", 0),
                "resume_id": f"resume_{i}",
            }
            print("=" * 50)
            print(f"✅ Processed : {result_data}")
            print("=" * 50)

            all_results.append(result_data)
            st.success(f"✅ Processed {name} - Score: {score}")

        except Exception as e:
            st.error(f"❌ Error processing {filename}: {str(e)}")
            # Print full traceback for debugging
            import traceback
            st.error(traceback.format_exc())
            continue

    return all_results

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
        
        /* score styling */
        .score-high { color: #10b981; font-weight: bold; }
        .score-medium { color: #f59e0b; font-weight: bold; }
        .score-low { color: #ef4444; font-weight: bold; }
        </style>
        """,
        unsafe_allow_html=True,
    )

def get_score_class(score):
    """Return CSS class based on score"""
    if score >= 7:
        return "score-high"
    elif score >= 5:
        return "score-medium"
    else:
        return "score-low"


def display_ranked_candidates(processed_resumes):
    print("=" * 50)
    print(f"--processed_resumes : {processed_resumes}")
    print("=" * 50)
    
    """
    Display ranked candidates with detailed information
    """
    if not processed_resumes:
        st.warning("⚠️ No candidates to display.")
        return

    # Rank candidates if not already ranked
    if not all("rank" in r for r in processed_resumes):
        try:
            ranked_resumes = rank_top_candidates(processed_resumes)
        except Exception as e:
            st.error(f"Error ranking candidates: {e}")
            # Fallback: sort by score
            ranked_resumes = sorted(processed_resumes, key=lambda x: x.get("score", 0), reverse=True)
            for i, res in enumerate(ranked_resumes, 1):
                res["rank"] = i
    else:
        ranked_resumes = processed_resumes

    st.subheader("🏆 Top Ranked Candidates")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Candidates", len(ranked_resumes))
    with col2:
        accepted = len([r for r in ranked_resumes if r.get("feedback") == "Accept"])
        st.metric("Accepted", accepted)
    with col3:
        avg_score = sum(r.get("score", 0) for r in ranked_resumes) / len(ranked_resumes) if ranked_resumes else 0
        st.metric("Avg Score", f"{avg_score:.2f}")
    with col4:
        top_score = max(r.get("score", 0) for r in ranked_resumes) if ranked_resumes else 0
        st.metric("Top Score", f"{top_score:.2f}")

    print("=" * 50)
    print(f"--Ranked_resumes : {ranked_resumes}")
    print("=" * 50)
    
    # Display candidates
    for i, res in enumerate(ranked_resumes[:10], 1):  # Show top 10
        
        # Debug print
        print("=" * 50)
        print(f"Candidate {i} data:", res)
        print("=" * 50)
        
        score = res.get('score', 0)
        score_class = get_score_class(score)
        
        # Better handling of missing name
        candidate_name = res.get('name', 'name') #or f"Temp_Candidate_{i}"
        if candidate_name == "None" or candidate_name is None:
            candidate_name = f"Temp_Candidate_{i}"
        
        with st.expander(f"🏅 Rank {i}: {candidate_name} (Score: {score})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📋 Basic Info")
                st.markdown(f"**Name:** {res.get('name', 'N/A') or 'N/A'}")
                st.markdown(f"**Email:** {res.get('email', 'N/A') or 'N/A'}")
                st.markdown(f"**Mobile:** {res.get('mobile', 'N/A') or 'N/A'}")
                st.markdown(f"**Job Type:** {res.get('job_type', 'Unknown') or 'Unknown'}")
                # st.markdown(f"**Filename:** {res.get('filename', 'N/A')}")
                
                # Feedback with color coding
                feedback = res.get('feedback', 'No feedback')
                if feedback == "Accept":
                    st.success(f"**Decision:** ✅ {feedback}")
                else:
                    st.error(f"**Decision:** ❌ {feedback}")
            
            with col2:
                st.markdown("### 📊 Scores & Analysis")
                st.markdown(f"**Final Score:** <span class='{score_class}'>{score}</span>", unsafe_allow_html=True)
                st.markdown(f"**Similarity Score:** {res.get('similarity_score', 'N/A')}")
                st.markdown(f"**Education:** {res.get('education', 'Unknown')}")
                st.markdown(f"**Experience:** {res.get('experience', '0')} years")
            
            # Skills section
            skills = res.get('skills', [])
            if skills and isinstance(skills, list):
                st.markdown("### 🔧 Skills")
                # Display skills as tags
                skills_html = " ".join([f"<span style='background:#e1f5fe; padding:4px 8px; border-radius:12px; margin:2px; display:inline-block; font-size:12px;'>{skill}</span>" for skill in skills[:10]])
                st.markdown(skills_html, unsafe_allow_html=True)
            
            # Resume link
            resume_path = res.get("resume_path") or res.get("filepath")
            if resume_path and os.path.exists(resume_path):
                st.markdown(f"📄 **Resume:** [View File]({resume_path})")
            
            # Debug section (remove in production)
            with st.expander("🐛 Debug Info"):
                st.json(res)

def run_streamlit():
    load_custom_css()
    st.set_page_config(page_title="HR Hiring Bot", layout="wide")

    # Initialize session state
    if "resume_items" not in st.session_state:
        st.session_state["resume_items"] = []
    if "jd_text" not in st.session_state:
        st.session_state["jd_text"] = ""
    if "jd_submitted" not in st.session_state:
        st.session_state["jd_submitted"] = False
    if "results" not in st.session_state:
        st.session_state["results"] = []
    if "processing_complete" not in st.session_state:
        st.session_state["processing_complete"] = False

    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("<h1>🤖 HR Hiring Bot - LangGraph Powered</h1>", unsafe_allow_html=True)
        st.markdown("<div class='muted'>AI-powered resume screening with LangGraph workflow</div>", unsafe_allow_html=True)

    # Sidebar: choose source
    source = st.sidebar.radio("🔎 Select Source", ["Gmail", "Upload Folder", "Manual Upload", "Google Drive", "View Results"])

    # Job Description section
    st.markdown("## 📄 Job Description")
    jd_col1, jd_col2 = st.columns([4, 1])
    
    with jd_col1:
        jd_text_input = st.text_area(
            "Paste Job Description here", 
            height=180, 
            value=st.session_state["jd_text"],
            placeholder="Enter the job description for AI-powered matching..."
        )
        jd_file = st.file_uploader("Optional: Upload JD file", type=["txt", "pdf"])
    
    with jd_col2:
        if st.button("✅ Submit Job Description"):
            final_jd_text = ""
            
            if jd_file is not None:
                if jd_file.name.lower().endswith(".pdf"):
                    tmp_dir = "temp_jd"
                    os.makedirs(tmp_dir, exist_ok=True)
                    tmp_path = os.path.join(tmp_dir, jd_file.name)
                    with open(tmp_path, "wb") as f:
                        f.write(jd_file.getbuffer())
                    try:
                        final_jd_text = extract_text_from_pdf(tmp_path)
                    except Exception as e:
                        st.error(f"Error extracting text from JD PDF: {e}")
                else:
                    try:
                        final_jd_text = jd_file.read().decode("utf-8")
                    except Exception:
                        st.error("Error reading text file")
            else:
                final_jd_text = jd_text_input

            if final_jd_text and final_jd_text.strip():
                st.session_state["jd_text"] = final_jd_text
                st.session_state["jd_submitted"] = True
                st.success("✅ Job Description submitted successfully!")
            else:
                st.warning("⚠️ Please provide a valid Job Description.")

    # Show JD status
    if st.session_state["jd_submitted"]:
        st.success("✅ Job Description ready for processing")
    else:
        st.info("ℹ️ Please submit Job Description to enable processing")

    st.markdown("---")

    # Source-specific sections
    if source == "Gmail":
        st.subheader("📩 Fetch Resumes from Gmail")
        
        with st.form("gmail_form"):
            col1, col2 = st.columns(2)
            
            
            submitted = st.form_submit_button("📥 Fetch Resumes")
            
            if submitted:
                user =os.getenv("GMAIL_USER")
                pwd = os.getenv("GMAIL_PASS")
                
                if not user or not pwd:
                    st.error("❌ Please provide Gmail credentials")
                else:
                    # with st.spinner("📡 Fetching resumes from Gmail..."):
                    #     try:
                    #         items = fetch_from_gmail(user, pwd, download_dir="resumes/gmail")
                    with st.spinner("📡 Fetching resumes from Gmail..."):
                        try:
                            state = {}
                            items_state = fetch_from_gmail(state, download_dir="resumes/gmail")
                            items = items_state.get("resumes", [])

                            st.session_state["resume_items"] = items or []
                            st.session_state["source_type"] = "gmail"
                            st.success(f"✅ Fetched {len(st.session_state['resume_items'])} resumes from Gmail")
                        except Exception as e:
                            st.error(f"❌ Error fetching from Gmail: {e}")

    elif source == "Upload Folder":
        st.subheader("📁 Upload Multiple Resumes")
        
        uploaded_files = st.file_uploader(
            "Upload resume files", 
            accept_multiple_files=True, 
            type=["pdf", "docx", "doc"],
            help="Upload multiple resume files at once"
        )
        
        if st.button("📂 Process Uploaded Files"):
            if not uploaded_files:
                st.warning("Please upload resume files")
            else:
                os.makedirs("temp_uploaded", exist_ok=True)
                saved_items = []
                
                for f in uploaded_files:
                    path = os.path.join("temp_uploaded", f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved_items.append({
                        "filepath": path,
                        "filename": f.name,
                        "sender_email": "Uploaded"
                    })
                
                st.session_state["resume_items"] = saved_items
                st.session_state["source_type"] = "folder"
                st.success(f"✅ Uploaded {len(saved_items)} files")

    elif source == "Manual Upload":
        st.subheader("📤 Manual Resume Upload")
        
        uploaded_files = st.file_uploader(
            "Upload resumes one by one", 
            accept_multiple_files=True, 
            type=["pdf", "docx", "doc"]
        )
        
        if st.button("📥 Add to Workspace"):
            if uploaded_files:
                os.makedirs("temp_manual", exist_ok=True)
                current_items = st.session_state.get("resume_items", [])
                
                for f in uploaded_files:
                    path = os.path.join("temp_manual", f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    current_items.append({
                        "filepath": path,
                        "filename": f.name,
                        "sender_email": "Manual Upload"
                    })
                
                st.session_state["resume_items"] = current_items
                st.session_state["source_type"] = "manual"
                st.success(f"✅ Added {len(uploaded_files)} resumes to workspace")

    elif source == "Google Drive":
        st.subheader("☁️ Fetch from Google Drive")
        st.info("This will fetch resumes from Google Drive using your credentials.json file")
        
        if st.button("📥 Fetch from Drive"):
            with st.spinner("📡 Fetching from Google Drive..."):
                try:
                    # Create initial state for drive fetch
                    initial_state = {
                        "source_type": "drive",
                        "jd_text": st.session_state.get("jd_text", ""),
                        "resume": None
                    }
                    
                    # This would trigger the drive fetch in your LangGraph
                    # For now, we'll simulate it
                    print("hi")
                    st.info("Drive integration ready - implement fetch_from_drive function")
                    print("heloo")
                    state = {} 
                    items = fetch_from_drive(initial_state)  # Implement this
                    print("next")
                    st.session_state["resume_items"] = items
                    st.session_state["source_type"] = "drive"
                    
                except Exception as e:
                    st.error(f"❌ Error fetching from Drive: {e}")
    

    elif source == "View Results":
        st.subheader("📊 Resume Processing & Results")

        # Debug: Print all session state keys/values
        for k, v in st.session_state.items():
            print(f"*******\nkey: {k}  --------- value: {v}")

        if st.session_state.get("resume_items"):
            st.markdown(f"**Workspace:** {len(st.session_state['resume_items'])} resumes loaded")

            
            with st.expander("📋 View loaded resumes"):
                for i, resume_item in enumerate(st.session_state["resume_items"], start=1):
                    
                    # Handle both dict and string formats
                    if isinstance(resume_item, dict):
                        filepath = resume_item.get("filepath", "")
                        filename = resume_item.get("filename", os.path.basename(filepath))
                        sender = resume_item.get("sender_email", "Unknown")
                    else:
                        filepath = resume_item
                        filename = os.path.basename(resume_item)
                        sender = st.session_state.get("sender_email", "Unknown")
                    
                    # Only display if filepath is not empty
                    if filepath:
                        st.markdown(
                            f"{i}. [{filename}](file:///{filepath}) (from: {sender})",
                            unsafe_allow_html=True
                        )
                    else:
                        st.write(f"{i}. ❌ Invalid resume entry")


        else:
            st.info("No resumes in workspace. Use other tabs to load resumes.")

    

    
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("⚙️ Start Processing", disabled=not (st.session_state["resume_items"] and st.session_state["jd_submitted"])):
                if not st.session_state["resume_items"]:
                    st.error("Please load resumes first")
                elif not st.session_state["jd_submitted"]:
                    st.error("Please submit Job Description first")
                else:
                    with st.spinner("🔄 Processing resumes with LangGraph..."):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        try:
                            source_type = st.session_state.get("source_type", "manual")
                            results = process_resumes(
                                st.session_state["resume_items"], 
                                st.session_state["jd_text"],
                                source_type
                            )
                            print("=" * 50)
                            print(f"--Results : {results}")
                            print("=" * 50)
                            
                            st.session_state["results"] = results
                            st.session_state["processing_complete"] = True
                            progress_bar.progress(100)
                            status_text.success(f"✅ Processed {len(results)} resumes!")
                            
                        except Exception as e:
                            st.error(f"❌ Processing error: {e}")

        with col2:
            if st.button("🧹 Clear Workspace"):
                st.session_state["resume_items"] = []
                st.session_state["results"] = []
                st.session_state["processing_complete"] = False
                st.success("Workspace cleared")

        with col3:
            if st.session_state["results"]:
                # Download results as JSON
                results_json = json.dumps(st.session_state["results"], indent=2)
                st.download_button(
                    "📥 Download Results",
                    results_json,
                    "resume_analysis_results.json",
                    "application/json"
                )

        # Display results
        if st.session_state["results"]:
            display_ranked_candidates(st.session_state["results"])
        elif st.session_state["processing_complete"]:
            st.warning("Processing completed but no valid results found.")

    # Footer
   

if __name__ == "__main__":
    run_streamlit()






















































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
