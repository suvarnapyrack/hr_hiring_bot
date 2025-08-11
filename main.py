


















# import os
# import re
# import pdfplumber
# import imaplib
# import email
# import streamlit as st
# from dotenv import load_dotenv
# from datetime import datetime, timedelta
# from app.langgraph_flow import graph
# from app.utils import fetch_resumes_from_gmail, extract_text_from_pdf,extract_mobile #, send_feedback_email

# load_dotenv()








    




# from app.utils import extract_text_from_pdf
# from app.langgraph_flow import graph  # Make sure graph is defined and imported

# from app.utils import score_resume
# def process_resumes(resume_items, jd_text):
#     all_results = []

#     for i, item in enumerate(resume_items):
#         path = item["filepath"]
#         sender = item.get("sender_email", "Unknown")
#         resume_text = extract_text_from_pdf(path)

#         state = {
#             "jd_text": jd_text,
#             "resume": resume_text,
#             "resume_text": resume_text,  # ✅ ADD this line for ranking
#             "resume_path": path,
#             "resume_id": f"resume_{i}",
#             "sender_email": sender,
#             "mobile": extract_mobile(resume_text)  # Extract mobile number from resume text
#         }

#         # Step 1: Run LangGraph
#         state = graph.invoke(state)

#         # Step 2: Apply scoring
#         state = score_resume(state)

#         # Step 3: Skip resumes with low experience
#         if state.get("experience_filtered"):
#             continue

#         # Step 4: Collect results
#         name = state.get("name", f"Candidate {i+1}")
#         email = state.get("email", sender)
#         score = state.get("score", 0)
#         feedback = "Accept" if score >= 6.5 else "Reject"

#         # ✅ Append all required fields
#         all_results.append({
#             "name": name,
#             "email": email,
#             "score": score,
#             "feedback": feedback,
#             "mobile": state.get("mobile", "Not available"),
#             "resume_path": path,
#             "resume_text": resume_text,     # ✅ needed for ranking
#             "resume_id": f"resume_{i}",     # ✅ optional, used in utils
#         })

#     return all_results














# import os
# import streamlit as st
# from app.utils import (
#     extract_text_from_pdf,            # PDF text extractor (your existing function)
#     fetch_resumes_from_gmail,        # should return list of resume items (e.g. dicts with filepath or bytes)
#     # process_resumes,                 # your existing pipeline that scores resumes vs jd_text
#     rank_top_candidates              # optional ranking function (fallback)
# )

# # -----------------------
# # UI / CSS
# # -----------------------
# def load_custom_css():
#     st.markdown(
#         """
#         <style>
#         /* page background */
#         .stApp {
#             background: linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
#             font-family: 'Inter', sans-serif;
#         }

#         /* header */
#         h1 { color: #05386B; font-weight: 800; }

#         /* sidebar - light */
#         [data-testid="stSidebar"] {
#             background: #fbfdff;
#             border-right: 1px solid #e6eef6;
#         }

#         /* buttons */
#         .stButton>button {
#             background: linear-gradient(90deg,#0077b6,#00b4d8);
#             color: white;
#             border-radius: 10px;
#             padding: 8px 14px;
#             font-weight: 600;
#         }
#         .stButton>button:hover { transform: translateY(-2px); }

#         /* candidate cards */
#         .candidate-card {
#             background: #ffffff;
#             padding: 14px;
#             border-radius: 12px;
#             box-shadow: 0 6px 18px rgba(3, 23, 55, 0.06);
#             margin-bottom: 12px;
#         }

#         /* small helper */
#         .muted { color: #6b7280; font-size: 13px; }
#         </style>
#         """,
#         unsafe_allow_html=True,
#     )


# # -----------------------
# # Helper: Display results (expander style)
# # -----------------------
# def display_ranked_candidates(processed_resumes):
#     """
#     Accepts a list of processed resume dicts. Each dict ideally contains:
#       - name, email, mobile, score, feedback, resume_path
#     If processed_resumes is not ranked, attempt to call rank_top_candidates() to compute ordering.
#     """
#     if not processed_resumes:
#         st.warning("⚠️ No candidates to display.")
#         return

#     # If items don't have a 'rank' key, attempt to rank them using rank_top_candidates
#     need_rank = not all("rank" in r for r in processed_resumes)
#     if need_rank:
#         try:
#             top = rank_top_candidates(processed_resumes)
#         except Exception:
#             # fallback: simple sort by 'score' if present
#             top = sorted(processed_resumes, key=lambda x: x.get("score", 0), reverse=True)
#         processed_resumes = top

#     st.subheader("🏆 Top Ranked Candidates")
#     for i, res in enumerate(processed_resumes, 1):
#         with st.expander(f"📌 Candidate {i}: {res.get('name','Unknown')}"):
#             st.markdown(f"📧 **Email:** {res.get('email','N/A')}")
#             st.markdown(f"📱 **Mobile:** {res.get('mobile','N/A')}")
#             st.markdown(f"💯 **Score:** {res.get('score','N/A')}")
#             st.markdown(f"📝 **Feedback:** `{res.get('feedback','No feedback')}`")
#             resume_link = res.get("resume_path") or res.get("filepath") or "#"
#             st.markdown(f"📄 **Resume:** [Open Resume]({resume_link})")

# # -----------------------
# # Main app
# # -----------------------
# def run_streamlit():
#     load_custom_css()
#     st.set_page_config(page_title="HR Hiring Bot", layout="wide")

#     # initialize session state
#     if "resume_items" not in st.session_state:
#         st.session_state["resume_items"] = []   # list of resume dicts or {"filepath":...}
#     if "jd_text" not in st.session_state:
#         st.session_state["jd_text"] = ""
#     if "jd_submitted" not in st.session_state:
#         st.session_state["jd_submitted"] = False
#     if "results" not in st.session_state:
#         st.session_state["results"] = []

#     # top/header
#     col1, col2 = st.columns([3, 1])
#     with col1:
#         st.markdown("<h1>🤖 HR Hiring Bot</h1>", unsafe_allow_html=True)
#         st.markdown("<div class='muted'>Fetch resumes from Gmail / folder / manual upload → Submit JD → Rank candidates</div>", unsafe_allow_html=True)
#     with col2:
#         st.markdown("")  # reserved

#     # Sidebar: choose source
#     source = st.sidebar.radio("🔎 Select Source", ["Gmail", "Upload Folder", "Manual Upload", "View Results"])

#     # -------------------------
#     # Job Description area (main)
#     # -------------------------
#     st.markdown("## 📄 Job Description")
#     jd_col1, jd_col2 = st.columns([4,1])
#     with jd_col1:
#         jd_text_input = st.text_area("Paste Job Description here (or upload JD file below)", height=180, value=st.session_state["jd_text"])
#         jd_file = st.file_uploader("Optional: Upload JD (txt, pdf)", type=["txt","pdf"], help="If you upload a JD file it will replace the text area.")
#     with jd_col2:
#         if st.button("✅ Submit Job Description"):
#             # if file uploaded, extract text (if pdf use extract_text_from_pdf)
#             final_jd_text = ""
#             if jd_file is not None:
#                 if jd_file.name.lower().endswith(".pdf"):
#                     # save temporarily and call your extractor
#                     tmp_dir = "temp_jd"
#                     os.makedirs(tmp_dir, exist_ok=True)
#                     tmp_path = os.path.join(tmp_dir, jd_file.name)
#                     with open(tmp_path, "wb") as f:
#                         f.write(jd_file.getbuffer())
#                     try:
#                         final_jd_text = extract_text_from_pdf(tmp_path)
#                     except Exception as e:
#                         st.error("Error extracting text from JD PDF: " + str(e))
#                         final_jd_text = ""
#                 else:
#                     try:
#                         final_jd_text = jd_file.read().decode("utf-8")
#                     except Exception:
#                         final_jd_text = ""
#             else:
#                 final_jd_text = jd_text_input

#             if final_jd_text and final_jd_text.strip():
#                 st.session_state["jd_text"] = final_jd_text
#                 st.session_state["jd_submitted"] = True
#                 st.success("✅ Job Description submitted. You can now rank resumes.")
#             else:
#                 st.warning("⚠️ Please paste or upload a valid Job Description before submitting.")

#     # Show current JD status
#     if st.session_state["jd_submitted"]:
#         st.info("✅ JD submitted. Ready for ranking.")
#     else:
#         st.info("ℹ️ JD not submitted yet — you can still fetch resumes and save them, then submit JD when ready.")

#     st.markdown("---")

#     # -------------------------
#     # Source-specific UI
#     # -------------------------
#     if source == "Gmail":
#         st.subheader("📩 Fetch from Gmail")
#         with st.form("gmail_form", clear_on_submit=False):
#             gmail_user = st.text_input("Gmail Username (or leave empty to use env)")
#             gmail_pass = st.text_input("Gmail App Password / OAuth token", type="password")
#             submitted = st.form_submit_button("📥 Fetch from Gmail")
#             if submitted:
#                 user = gmail_user.strip() or os.getenv("GMAIL_USER")
#                 pwd = gmail_pass.strip() or os.getenv("GMAIL_PASS")
#                 if not user or not pwd:
#                     st.error("❌ Gmail credentials not provided (env or field).")
#                 else:
#                     with st.spinner("📡 Fetching resumes from Gmail..."):
#                         try:
#                             items = fetch_resumes_from_gmail(user, pwd)
#                             # expected items: list of dicts (e.g. {'filepath': '/path/...', ...})
#                             st.session_state["resume_items"] = items or []
#                             st.success(f"✅ Fetched {len(st.session_state['resume_items'])} resumes from Gmail.")
#                         except Exception as e:
#                             st.error("Error fetching from Gmail: " + str(e))

#         # show small preview of fetched files
#         if st.session_state["resume_items"]:
#             st.markdown("**Fetched resumes (preview):**")
#             for r in st.session_state["resume_items"][:10]:
#                 st.write("- " + (r.get("sender_email") or r.get("filename") or r.get("filepath", "Unknown")))

#     elif source == "Upload Folder":
#         st.subheader("📁 Upload Folder (multiple resumes)")
#         st.markdown("Upload multiple resumes (pdf / docx) — they will be saved temporarily and listed.")
#         uploaded_files = st.file_uploader("Upload multiple resumes", accept_multiple_files=True, type=["pdf","docx","doc"])
#         if st.button("📂 Save uploaded files"):
#             if not uploaded_files:
#                 st.warning("Please upload one or more resume files.")
#             else:
#                 os.makedirs("temp_uploaded", exist_ok=True)
#                 saved = []
#                 for f in uploaded_files:
#                     path = os.path.join("temp_uploaded", f.name)
#                     with open(path, "wb") as out:
#                         out.write(f.getbuffer())
#                     saved.append({"filepath": path, "sender_email": "N/A", "filename": f.name})
#                 st.session_state["resume_items"] = saved
#                 st.success(f"✅ Saved {len(saved)} files to temp_uploaded.")
#         if st.session_state["resume_items"]:
#             st.markdown("**Recently uploaded resumes:**")
#             for r in st.session_state["resume_items"]:
#                 st.write("- " + (r.get("filename") or r.get("filepath")))

#     elif source == "Manual Upload":
#         st.subheader("📤 Manual Upload (single or multiple resumes)")
#         uploaded_files = st.file_uploader("Upload resume(s)", accept_multiple_files=True, type=["pdf","docx","doc"])
#         if st.button("📥 Add to workspace"):
#             if not uploaded_files:
#                 st.warning("Please upload resume(s).")
#             else:
#                 os.makedirs("temp_uploaded", exist_ok=True)
#                 added = st.session_state.get("resume_items", [])
#                 for f in uploaded_files:
#                     path = os.path.join("temp_uploaded", f.name)
#                     with open(path, "wb") as out:
#                         out.write(f.getbuffer())
#                     added.append({"filepath": path, "sender_email": "Manual Upload", "filename": f.name})
#                 st.session_state["resume_items"] = added
#                 st.success(f"✅ Added {len(uploaded_files)} resumes to workspace.")

#         if st.session_state["resume_items"]:
#             st.markdown("**Current workspace resumes (click View Results to see ranked output after submitting JD):**")
#             for r in st.session_state["resume_items"]:
#                 st.write("- " + (r.get("filename") or r.get("filepath")))

#     elif source == "View Results":
#         st.subheader("🧾 Workspace & Results")
#         st.markdown("You can fetch/add resumes from any source (Gmail / Upload folder / Manual). They are stored temporarily in the workspace. Then submit a JD and click **Rank & Process** below to score them.")

#         st.markdown("**Workspace resumes:**")
#         if not st.session_state["resume_items"]:
#             st.info("No resumes in workspace yet. Use Gmail / Upload / Manual to add resumes.")
#         else:
#             for r in st.session_state["resume_items"]:
#                 st.write("- " + (r.get("filename") or r.get("filepath") or r.get("sender_email", "resume")))

#         colA, colB = st.columns(2)
#         with colA:
#             if st.button("⚙️ Rank & Process resumes (use submitted JD)"):
#                 if not st.session_state["resume_items"]:
#                     st.warning("Please add/fetch resumes first.")
#                 elif not st.session_state["jd_submitted"]:
#                     st.warning("Please submit the Job Description first (top-right).")
#                 else:
#                     with st.spinner("⚙️ Processing & scoring resumes..."):
#                         try:
#                             # process_resumes should return a list of result dicts
#                             results = process_resumes(st.session_state["resume_items"], st.session_state["jd_text"])
#                             st.session_state["results"] = results or []
#                             st.success("✅ Resume processing completed!")
#                         except Exception as e:
#                             st.error("Error during resume processing: " + str(e))
#         with colB:
#             if st.button("🧹 Clear workspace"):
#                 st.session_state["resume_items"] = []
#                 st.session_state["results"] = []
#                 st.success("Workspace cleared.")

#         # show processed results if present
#         if st.session_state["results"]:
#             display_ranked_candidates(st.session_state["results"])
#         else:
#             st.info("No processed results yet. After ranking, results will appear here.")

#     # small footer
#     # st.markdown("---")
#     # st.markdown("💡 Tip: You can fetch resumes first (Gmail / Upload), submit JD anytime, then use **View Results → Rank & Process** to get the ranked candidates.")

# # run
# if __name__ == "__main__":
#     run_streamlit()




# import streamlit as st
# import os
# import pdfplumber


# from dotenv import load_dotenv
# load_dotenv()

# import os
# import streamlit as st
# from email.mime.text import MIMEText
# import smtplib


# import re


# def extract_email(raw_email):
#     match = re.search(r'<(.+?)>', raw_email)
#     return match.group(1).strip() if match else raw_email.strip()



















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
# from app import create_resume_processing_graph
# # Create the graph instance#
# graph = create_resume_processing_graph()

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
            # If item is just a string path
            path = item
            sender = "Unknown"
            filename = f"resume_{i}"

        if not path or not os.path.exists(path):
            st.warning(f"⚠️ File not found: {path}")
            continue

        try:
            # Create initial state for this resume
            initial_state = {
                "source_type": source_type,
                "jd_text": jd_text,
                "resume": path,  # File path
                "resume_text": "",  # Will be filled by parse_resume
                "mobile": "",   # Will be filled by parse_resume
                "similarity_score": 0,
                "llm_score": 0,
                "embedding_score": 0,
                "job_type": "",
                "analysis": {},
                "score": 0,
                "experience_filtered": False,
                "rank": 0
            }

            # Run the LangGraph pipeline
            result_state = graph.invoke(initial_state)

            # Extract name from analysis or use default
            analysis = result_state.get("analysis", {})
            name = f"Candidate {i+1}"  # You can enhance this by extracting name from resume
            
            # Determine feedback based on score
            score = result_state.get("score", 0)
            feedback = "Accept" if score >= 6.5 else "Reject"

            # Skip if filtered by experience
            if result_state.get("experience_filtered", False):
                feedback = "Rejected (Experience)"
                st.info(f"📋 {name}: Filtered out due to insufficient experience")

            # Collect results
            result_data = {
                "name": name,
                "email": sender,
                "score": score,
                "feedback": feedback,
                "mobile": result_state.get("mobile", "Not available"),
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

            all_results.append(result_data)
            st.success(f"✅ Processed {name} - Score: {score}")

        except Exception as e:
            st.error(f"❌ Error processing {filename}: {str(e)}")
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

    # Display candidates
    for i, res in enumerate(ranked_resumes[:10], 1):  # Show top 10
        score = res.get('score', 0)
        score_class = get_score_class(score)
        
        with st.expander(f"🏅 Rank {i}: {res.get('name','Unknown')} (Score: {score})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📋 Basic Info")
                st.markdown(f"**Name:** {res.get('name','Unknown')}")
                st.markdown(f"**Email:** {res.get('email','N/A')}")
                st.markdown(f"**Mobile:** {res.get('mobile','N/A')}")
                st.markdown(f"**Job Type:** {res.get('job_type','Unknown')}")
                
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
                st.markdown(f"**LLM Score:** {res.get('llm_score', 'N/A')}")
                st.markdown(f"**Embedding Score:** {res.get('embedding_score', 'N/A')}")
                st.markdown(f"**Education:** {res.get('education', 'Unknown')}")
                st.markdown(f"**Experience:** {res.get('experience', '0')} years")
            
            # Skills section
            skills = res.get('skills', [])
            if skills:
                st.markdown("### 🔧 Skills")
                # Display skills as tags
                skills_html = " ".join([f"<span style='background:#e1f5fe; padding:4px 8px; border-radius:12px; margin:2px; display:inline-block; font-size:12px;'>{skill}</span>" for skill in skills[:10]])
                st.markdown(skills_html, unsafe_allow_html=True)
            
            # Resume link
            resume_path = res.get("resume_path") or res.get("filepath")
            if resume_path and os.path.exists(resume_path):
                st.markdown(f"📄 **Resume:** [Download]({resume_path})")

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
            # with col1:
            #     gmail_user = st.text_input("Gmail Username", placeholder="your-email@gmail.com")
            # with col2:
                # gmail_pass = st.text_input("App Password", type="password", help="Generate app password in Gmail settings")
            
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
        
       
       
        for i in st.session_state:
            print("*******")
            print(f"key {i}  --------- value {st.session_state[i]}")


        if st.session_state["resume_items"]:
            st.markdown(f"**Workspace:** {len(st.session_state['resume_items'])} resumes loaded")
            print("hiii           ",st.markdown(f"**Workspace:** {len(st.session_state['resume_items'])} resumes loaded"))
            # Show preview
            with st.expander("📋 View loaded resumes"):
                for i, item in enumerate(st.session_state["resume_items"], 0):
                    filename = st.session_state.get("resume")
                    sender = st.session_state.get("sender_email", "Unknown")
                    st.write(f"{i}. **{filename}** (from: {sender})")
        else:
            st.info("No resumes in workspace. Use other tabs to load resumes.")

    
        # if "resume_items" not in st.session_state:
        #     st.session_state["resume_items"] = []

        # elif isinstance(st.session_state["resume_items"], dict):
        #     st.session_state["resume_items"] = [st.session_state["resume_items"]]

        # Now safe to append
        # st.session_state["resume_items"].append({
        #     "resume": uploaded_resume_path,
        #     "jd_text": st.session_state["jd_text"],
        #     "source_type": "drive"
        # })




      



        # Processing section
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
