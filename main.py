


# import os
# import re
# import streamlit as st
# from dotenv import load_dotenv
# from datetime import datetime, timedelta
# import json
# import pandas as pd

# # Import your updated functions
# from app.utils import rank_top_candidates, fetch_from_gmail, fetch_from_drive 
# from app.utils import extract_text_from_pdf, parse_resume
# from app.langgraph_flow import graph
# from typing import Dict

# load_dotenv()

# def process_resumes(resume_items, jd_text, source_type="manual"):
#     """Process multiple resumes using the LangGraph pipeline"""
#     all_results = []

#     for i, item in enumerate(resume_items):
#         if isinstance(item, dict):
#             path = item.get("filepath") or item.get("file_path")
#             sender = item.get("sender_email", "Unknown")
#             filename = item.get("filename", f"resume_{i}")
#         else:
#             path = item
#             sender = "Unknown"
#             filename = f"resume_{i}"

#         if not path or not os.path.exists(path):
#             st.warning(f"⚠️ File not found: {path}")
#             continue

#         try:
#             resume_text = ""
#             if path.lower().endswith('.pdf'):
#                 resume_text = extract_text_from_pdf(path)
#             elif path.lower().endswith(('.docx', '.doc')):
#                 with open(path, 'r', encoding='utf-8') as f:
#                     resume_text = f.read()
            
#             if not resume_text.strip():
#                 st.warning(f"⚠️ Could not extract text from: {filename}")
#                 continue

#             initial_state = {
#                 "source_type": source_type,
#                 "jd_text": jd_text,
#                 "resume": path,
#                 "resume_text": resume_text,
#                 "mobile": "",
#                 "email": "",
#                 "name": "",
#                 "similarity_score": 0,
#                 "llm_score": 0,
#                 "embedding_score": 0,
#                 "job_type": "",
#                 "analysis": {},
#                 "score": 0,
#                 "experience_filtered": False,
#                 "rank": 0,
#                 "address": ""
#             }

#             parsed_state = parse_resume(initial_state)
            
#             st.info(f"🔍 Parsing: {filename}")
#             st.info(f"   📝 {parsed_state.get('name', 'Not found')} | 📧 {parsed_state.get('email', 'Not found')}")

#             result_state = graph.invoke(parsed_state)

#             name = result_state.get("name")
#             email = result_state.get("email")
#             mobile = result_state.get("mobile")
#             address = result_state.get("address")

#             score = result_state.get("score", 0)
#             feedback = "Accept" if score >= 6.5 else "Reject"

#             if result_state.get("experience_filtered", False):
#                 feedback = "Rejected (Experience)"
#                 st.info(f"📋 {name}: Filtered out due to insufficient experience")

#             analysis = result_state.get("analysis", {})

#             result_data = {
#                 "name": name,
#                 "email": email,
#                 "score": score,
#                 "feedback": feedback,
#                 "mobile": mobile,
#                 "address": address,
#                 "resume_path": path,
#                 "filename": filename,
#                 "job_type": result_state.get("job_type", "Unknown"),
#                 "skills": analysis.get("skills", []),
#                 "education": analysis.get("education", "Unknown"),
#                 "experience": analysis.get("experience", "0"),
#                 "similarity_score": result_state.get("similarity_score", 0),
#                 "llm_score": result_state.get("llm_score", 0),
#                 "embedding_score": result_state.get("embedding_score", 0),
#                 "resume_id": f"resume_{i}",
#             }

#             all_results.append(result_data)
#             st.success(f"✅ Processed {name} - Score: {score}")

#         except Exception as e:
#             st.error(f"❌ Error processing {filename}: {str(e)}")
#             import traceback
#             st.error(traceback.format_exc())
#             continue

#     return all_results

# def load_custom_css():
#     st.markdown("""
#         <style>
#         @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
        
#         /* Global Styles */
#         .stApp {
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             font-family: 'Inter', sans-serif;
#         }
        
#         /* Main container with glass effect */
#         .main .block-container {
#             background: rgba(255, 255, 255, 0.95);
#             backdrop-filter: blur(10px);
#             border-radius: 24px;
#             padding: 2rem 3rem;
#             box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
#             margin-top: 2rem;
#         }
        
#         /* Header styling */
#         h1 {
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             -webkit-background-clip: text;
#             -webkit-text-fill-color: transparent;
#             font-weight: 800;
#             font-size: 3rem !important;
#             margin-bottom: 0.5rem !important;
#             letter-spacing: -1px;
#         }
        
#         h2 {
#             color: #1e293b;
#             font-weight: 700;
#             font-size: 1.8rem !important;
#             margin-top: 2rem !important;
#             margin-bottom: 1rem !important;
#         }
        
#         h3 {
#             color: #475569;
#             font-weight: 600;
#             font-size: 1.2rem !important;
#         }
        
#         /* Sidebar styling */
#         [data-testid="stSidebar"] {
#             background: linear-gradient(180deg, #1e293b 0%, #334155 100%);
#             border-right: none;
#         }
        
#         [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
#             color: #e2e8f0;
#         }
        
#         [data-testid="stSidebar"] .stRadio label {
#             color: #e2e8f0 !important;
#             font-weight: 500;
#             padding: 0.75rem 1rem;
#             border-radius: 12px;
#             transition: all 0.3s ease;
#         }
        
#         [data-testid="stSidebar"] .stRadio label:hover {
#             background: rgba(255, 255, 255, 0.1);
#         }
        
#         /* Button styling */
#         .stButton > button {
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             color: white;
#             border: none;
#             border-radius: 12px;
#             padding: 0.75rem 2rem;
#             font-weight: 600;
#             font-size: 1rem;
#             transition: all 0.3s ease;
#             box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
#         }
        
#         .stButton > button:hover {
#             transform: translateY(-2px);
#             box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
#         }
        
#         .stButton > button:active {
#             transform: translateY(0);
#         }
        
#         /* Metric cards */
#         [data-testid="stMetricValue"] {
#             font-size: 2rem !important;
#             font-weight: 700;
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             -webkit-background-clip: text;
#             -webkit-text-fill-color: transparent;
#         }
        
#         [data-testid="stMetricLabel"] {
#             color: #64748b;
#             font-weight: 600;
#             font-size: 0.9rem !important;
#         }
        
#         div[data-testid="metric-container"] {
#             background: white;
#             padding: 1.5rem;
#             border-radius: 16px;
#             box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
#             border: 1px solid #e2e8f0;
#         }
        
#         /* Text area styling */
#         .stTextArea textarea {
#             border-radius: 12px;
#             border: 2px solid #e2e8f0;
#             padding: 1rem;
#             font-size: 0.95rem;
#             transition: all 0.3s ease;
#         }
        
#         .stTextArea textarea:focus {
#             border-color: #667eea;
#             box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
#         }
        
#         /* File uploader */
#         [data-testid="stFileUploader"] {
#             background: white;
#             border-radius: 16px;
#             border: 2px dashed #cbd5e1;
#             padding: 2rem;
#             transition: all 0.3s ease;
#         }
        
#         [data-testid="stFileUploader"]:hover {
#             border-color: #667eea;
#             background: #f8fafc;
#         }
        
#         /* Expander styling */
#         .streamlit-expanderHeader {
#             background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
#             border-radius: 12px;
#             padding: 1rem 1.5rem;
#             border: 1px solid #e2e8f0;
#             font-weight: 600;
#             color: #1e293b;
#         }
        
#         .streamlit-expanderHeader:hover {
#             border-color: #667eea;
#         }
        
#         /* Success/Error/Warning messages */
#         .stSuccess {
#             background: linear-gradient(135deg, #10b981 0%, #059669 100%);
#             color: white;
#             border-radius: 12px;
#             padding: 1rem 1.5rem;
#             border: none;
#         }
        
#         .stError {
#             background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
#             color: white;
#             border-radius: 12px;
#             padding: 1rem 1.5rem;
#             border: none;
#         }
        
#         .stWarning {
#             background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
#             color: white;
#             border-radius: 12px;
#             padding: 1rem 1.5rem;
#             border: none;
#         }
        
#         .stInfo {
#             background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
#             color: white;
#             border-radius: 12px;
#             padding: 1rem 1.5rem;
#             border: none;
#         }
        
#         /* DataTable styling */
#         .dataframe {
#             border-radius: 12px !important;
#             overflow: hidden;
#             box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08) !important;
#         }
        
#         .dataframe thead tr th {
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
#             color: white !important;
#             font-weight: 700 !important;
#             padding: 1rem !important;
#             border: none !important;
#         }
        
#         .dataframe tbody tr:hover {
#             background: #f8fafc !important;
#         }
        
#         .dataframe tbody tr td {
#             padding: 0.75rem 1rem !important;
#             border-bottom: 1px solid #e2e8f0 !important;
#         }
        
#         /* Score badges in table */
#         .score-badge-high {
#             background: #d1fae5;
#             color: #065f46;
#             padding: 0.35rem 0.75rem;
#             border-radius: 12px;
#             font-weight: 600;
#             display: inline-block;
#         }
        
#         .score-badge-medium {
#             background: #fef3c7;
#             color: #92400e;
#             padding: 0.35rem 0.75rem;
#             border-radius: 12px;
#             font-weight: 600;
#             display: inline-block;
#         }
        
#         .score-badge-low {
#             background: #fee2e2;
#             color: #991b1b;
#             padding: 0.35rem 0.75rem;
#             border-radius: 12px;
#             font-weight: 600;
#             display: inline-block;
#         }
        
#         /* Skill tags */
#         .skill-tag {
#             background: linear-gradient(135deg, #e0e7ff 0%, #ddd6fe 100%);
#             color: #5b21b6;
#             padding: 0.35rem 0.75rem;
#             border-radius: 20px;
#             margin: 0.15rem;
#             display: inline-block;
#             font-size: 0.75rem;
#             font-weight: 600;
#             box-shadow: 0 2px 8px rgba(91, 33, 182, 0.1);
#         }
        
#         /* Progress bar */
#         .stProgress > div > div {
#             background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
#             border-radius: 10px;
#         }
        
#         /* Divider */
#         hr {
#             margin: 2rem 0;
#             border: none;
#             height: 1px;
#             background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
#         }
        
#         /* Cards for candidates */
#         .candidate-card {
#             background: white;
#             border-radius: 16px;
#             padding: 1.5rem;
#             box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
#             border: 1px solid #e2e8f0;
#             transition: all 0.3s ease;
#             margin-bottom: 1rem;
#         }
        
#         .candidate-card:hover {
#             transform: translateY(-4px);
#             box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
#         }
        
#         /* Badge styles */
#         .badge {
#             display: inline-block;
#             padding: 0.35rem 0.75rem;
#             border-radius: 12px;
#             font-size: 0.85rem;
#             font-weight: 600;
#             margin: 0.25rem;
#         }
        
#         .badge-accept {
#             background: #d1fae5;
#             color: #065f46;
#         }
        
#         .badge-reject {
#             background: #fee2e2;
#             color: #991b1b;
#         }
        
#         /* Form styling */
#         .stForm {
#             background: white;
#             border-radius: 16px;
#             padding: 2rem;
#             box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
#             border: 1px solid #e2e8f0;
#         }
        
#         /* Download button special styling */
#         .stDownloadButton > button {
#             background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
#         }
        
#         .stDownloadButton > button:hover {
#             box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
#         }
        
#         /* Select box styling */
#         .stSelectbox > div > div {
#             border-radius: 12px;
#             border: 2px solid #e2e8f0;
#         }
        
#         /* Tab styling */
#         .stTabs [data-baseweb="tab-list"] {
#             gap: 8px;
#         }
        
#         .stTabs [data-baseweb="tab"] {
#             border-radius: 12px;
#             padding: 0.75rem 1.5rem;
#             background: white;
#             border: 2px solid #e2e8f0;
#             font-weight: 600;
#         }
        
#         .stTabs [aria-selected="true"] {
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             color: white;
#             border-color: transparent;
#         }
#         </style>
#     """, unsafe_allow_html=True)

# def get_score_badge_html(score):
#     """Return HTML badge based on score"""
#     if score >= 7:
#         return f'<span class="score-badge-high">⭐ {score:.2f}</span>'
#     elif score >= 5:
#         return f'<span class="score-badge-medium">📊 {score:.2f}</span>'
#     else:
#         return f'<span class="score-badge-low">📉 {score:.2f}</span>'

# def display_results_table(processed_resumes):
#     """Display results in a sortable table format"""
#     if not processed_resumes:
#         st.warning("⚠️ No candidates to display.")
#         return

#     st.markdown("## 📊 Results Dashboard")
    
#     # Summary metrics
#     col1, col2, col3, col4 = st.columns(4)
#     with col1:
#         st.metric("📊 Total Candidates", len(processed_resumes))
#     with col2:
#         accepted = len([r for r in processed_resumes if r.get("feedback") == "Accept"])
#         st.metric("✅ Accepted", accepted)
#     with col3:
#         avg_score = sum(r.get("score", 0) for r in processed_resumes) / len(processed_resumes) if processed_resumes else 0
#         st.metric("📈 Avg Score", f"{avg_score:.2f}")
#     with col4:
#         top_score = max(r.get("score", 0) for r in processed_resumes) if processed_resumes else 0
#         st.metric("⭐ Top Score", f"{top_score:.2f}")

#     st.markdown("<br>", unsafe_allow_html=True)
    
#     # Sorting controls
#     col1, col2, col3 = st.columns([2, 2, 1])
#     with col1:
#         sort_column = st.selectbox(
#             "📋 Sort by:",
#             ["Final Score", "Name", "Email", "Experience", "Similarity Score", "LLM Score", "Embedding Score"],
#             index=0
#         )
#     with col2:
#         sort_order = st.selectbox(
#             "🔄 Order:",
#             ["Descending (High to Low)", "Ascending (Low to High)"],
#             index=0
#         )
#     with col3:
#         st.markdown("<br>", unsafe_allow_html=True)
#         view_mode = st.radio("View:", ["Table", "Cards"], horizontal=True)
    
#     # Map sort column to data field
#     sort_mapping = {
#         "Final Score": "score",
#         "Name": "name",
#         "Email": "email",
#         "Experience": "experience",
#         "Similarity Score": "similarity_score",
#         "LLM Score": "llm_score",
#         "Embedding Score": "embedding_score"
#     }
    
#     sort_field = sort_mapping[sort_column]
#     ascending = "Ascending" in sort_order
    
#     # Sort the data
#     try:
#         sorted_resumes = sorted(
#             processed_resumes,
#             key=lambda x: float(x.get(sort_field, 0)) if sort_field in ["score", "similarity_score", "llm_score", "embedding_score", "experience"] else str(x.get(sort_field, "")),
#             reverse=not ascending
#         )
#     except:
#         sorted_resumes = processed_resumes
    
#     # Add rank
#     for i, res in enumerate(sorted_resumes, 1):
#         res["rank"] = i
    
#     if view_mode == "Table":
#         # Table View
#         st.markdown("### 📋 Candidate Results Table")
        
#         # Prepare data for table
#         table_data = []
#         for res in sorted_resumes:
#             name = res.get('name', 'N/A') or f"Candidate_{res.get('rank', '?')}"
#             table_data.append({
#                 "Rank": res.get("rank", "-"),
#                 "Name": name,
#                 "Email": res.get("email", "N/A") or "N/A",
#                 "Mobile": res.get("mobile", "N/A") or "N/A",
#                 "Score": round(res.get("score", 0), 2),
#                 "Feedback": res.get("feedback", "N/A"),
#                 "Experience": res.get("experience", "0"),
#                 "Education": res.get("education", "Unknown"),
#                 "Job Type": res.get("job_type", "Unknown"),
#             })
        
#         # Create DataFrame
#         df = pd.DataFrame(table_data)
        
#         # Display table with custom styling
#         st.dataframe(
#             df,
#             use_container_width=True,
#             height=600,
#             hide_index=True,
#             column_config={
#                 "Rank": st.column_config.NumberColumn("🏅 Rank", width="small"),
#                 "Name": st.column_config.TextColumn("👤 Name", width="medium"),
#                 "Email": st.column_config.TextColumn("📧 Email", width="medium"),
#                 "Mobile": st.column_config.TextColumn("📱 Mobile", width="medium"),
#                 "Score": st.column_config.NumberColumn("⭐ Score", format="%.2f", width="small"),
#                 "Feedback": st.column_config.TextColumn("✅ Status", width="small"),
#                 "Experience": st.column_config.TextColumn("💼 Exp (yrs)", width="small"),
#                 "Education": st.column_config.TextColumn("🎓 Education", width="medium"),
#                 "Job Type": st.column_config.TextColumn("💼 Job Type", width="medium"),
#             }
#         )
        
#         # Download button
#         csv = df.to_csv(index=False)
#         st.download_button(
#             label="📥 Download Results as CSV",
#             data=csv,
#             file_name=f"candidate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
#             mime="text/csv",
#             use_container_width=True
#         )
        
#     else:
#         # Card View
#         st.markdown("### 🎴 Candidate Cards")
        
#         for res in sorted_resumes[:20]:  # Show top 20 in card view
#             score = res.get('score', 0)
            
#             candidate_name = res.get('name', 'N/A')
#             if not candidate_name or candidate_name == "None":
#                 candidate_name = f"Candidate_{res.get('rank', '?')}"
            
#             with st.expander(f"🏅 Rank {res.get('rank', '?')}: {candidate_name} · Score: {score:.2f}", expanded=False):
#                 col1, col2 = st.columns([1, 1])
                
#                 with col1:
#                     st.markdown("#### 👤 Profile")
#                     st.markdown(f"**Name:** {res.get('name', 'N/A') or 'N/A'}")
#                     st.markdown(f"**📧 Email:** {res.get('email', 'N/A') or 'N/A'}")
#                     st.markdown(f"**📱 Mobile:** {res.get('mobile', 'N/A') or 'N/A'}")
#                     st.markdown(f"**📍 Location:** {res.get('address', 'Unknown') or 'Unknown'}")
#                     st.markdown(f"**💼 Job Type:** {res.get('job_type', 'Unknown') or 'Unknown'}")
                    
#                     feedback = res.get('feedback', 'No feedback')
#                     if feedback == "Accept":
#                         st.markdown(f"<div class='badge badge-accept'>✅ {feedback}</div>", unsafe_allow_html=True)
#                     else:
#                         st.markdown(f"<div class='badge badge-reject'>❌ {feedback}</div>", unsafe_allow_html=True)
                
#                 with col2:
#                     st.markdown("#### 📊 Scores & Analysis")
#                     st.markdown(f"**Final Score:** {get_score_badge_html(score)}", unsafe_allow_html=True)
#                     st.markdown(f"**🎯 Similarity Score:** {res.get('similarity_score', 'N/A')}")
#                     st.markdown(f"**🤖 LLM Score:** {res.get('llm_score', 'N/A')}")
#                     st.markdown(f"**📊 Embedding Score:** {res.get('embedding_score', 'N/A')}")
#                     st.markdown(f"**🎓 Education:** {res.get('education', 'Unknown')}")
#                     st.markdown(f"**💼 Experience:** {res.get('experience', '0')} years")
                
#                 # Skills section
#                 skills = res.get('skills', [])
#                 if skills and isinstance(skills, list):
#                     st.markdown("#### 🔧 Skills")
#                     skills_html = " ".join([f"<span class='skill-tag'>{skill}</span>" for skill in skills[:15]])
#                     st.markdown(skills_html, unsafe_allow_html=True)
                
#                 # Resume file info
#                 resume_path = res.get("resume_path") or res.get("filepath")
#                 if resume_path and os.path.exists(resume_path):
#                     st.markdown(f"<br>📄 **Resume:** `{os.path.basename(resume_path)}`", unsafe_allow_html=True)

# def run_streamlit():
#     st.set_page_config(
#         page_title="HR Hiring Bot - AI Powered",
#         page_icon="🤖",
#         layout="wide",
#         initial_sidebar_state="expanded"
#     )
    
#     load_custom_css()

#     # Initialize session state
#     if "resume_items" not in st.session_state:
#         st.session_state["resume_items"] = []
#     if "jd_text" not in st.session_state:
#         st.session_state["jd_text"] = ""
#     if "jd_submitted" not in st.session_state:
#         st.session_state["jd_submitted"] = False
#     if "results" not in st.session_state:
#         st.session_state["results"] = []
#     if "processing_complete" not in st.session_state:
#         st.session_state["processing_complete"] = False

#     # Header
#     col1, col2 = st.columns([4, 1])
#     with col1:
#         st.markdown("<h1>🤖 HR Hiring Bot</h1>", unsafe_allow_html=True)
#         st.markdown("**AI-Powered Resume Screening with LangGraph Intelligence**")

#     # Sidebar navigation
#     with st.sidebar:
#         st.markdown("### 🎯 Navigation")
#         source = st.radio(
#             "",
#             ["📩 Gmail", "📁 Upload Folder", "📤 Manual Upload", "☁️ Google Drive", "📊 View Results"],
#             label_visibility="collapsed"
#         )
        
#         st.markdown("---")
#         st.markdown("### 📈 Quick Stats")
#         if st.session_state.get("resume_items"):
#             st.info(f"📁 **Loaded:** {len(st.session_state['resume_items'])} resumes")
#         if st.session_state.get("results"):
#             st.success(f"✅ **Processed:** {len(st.session_state['results'])} candidates")

#     # Job Description section
#     st.markdown("## 📄 Job Description")
    
#     jd_col1, jd_col2 = st.columns([5, 1])
    
#     with jd_col1:
#         jd_text_input = st.text_area(
#             "Paste Job Description", 
#             height=200, 
#             value=st.session_state["jd_text"],
#             placeholder="📝 Enter the complete job description for AI-powered candidate matching...",
#             help="Provide a detailed job description for better matching accuracy"
#         )
#         jd_file = st.file_uploader("📎 Or upload JD file (optional)", type=["txt", "pdf"])
    
#     with jd_col2:
#         st.markdown("<br>", unsafe_allow_html=True)
#         if st.button("✅ Submit JD", use_container_width=True):
#             final_jd_text = ""
            
#             if jd_file is not None:
#                 if jd_file.name.lower().endswith(".pdf"):
#                     tmp_dir = "temp_jd"
#                     os.makedirs(tmp_dir, exist_ok=True)
#                     tmp_path = os.path.join(tmp_dir, jd_file.name)
#                     with open(tmp_path, "wb") as f:
#                         f.write(jd_file.getbuffer())
#                     try:
#                         final_jd_text = extract_text_from_pdf(tmp_path)
#                     except Exception as e:
#                         st.error(f"Error extracting text: {e}")
#                 else:
#                     try:
#                         final_jd_text = jd_file.read().decode("utf-8")
#                     except Exception:
#                         st.error("Error reading file")
#             else:
#                 final_jd_text = jd_text_input

#             if final_jd_text and final_jd_text.strip():
#                 st.session_state["jd_text"] = final_jd_text
#                 st.session_state["jd_submitted"] = True
#                 st.success("✅ Job Description submitted successfully!")
#             else:
#                 st.warning("⚠️ Please provide a valid Job Description.")

#     # Status indicator
#     if st.session_state["jd_submitted"]:
#         st.success("✅ Job Description is ready for processing")
#     else:
#         st.info("💡 Submit a Job Description to enable resume processing")

#     st.markdown("---")

#     # Source-specific sections
#     if "Gmail" in source:
#         st.markdown("## 📩 Fetch Resumes from Gmail")
        
#         with st.form("gmail_form"):
#             st.info("📬 Connect to your Gmail account to fetch resumes automatically")
#             submitted = st.form_submit_button("📥 Fetch Resumes from Gmail", use_container_width=True)
            
#             if submitted:
#                 user = os.getenv("GMAIL_USER")
#                 pwd = os.getenv("GMAIL_PASS")
                
#                 if not user or not pwd:
#                     st.error("❌ Gmail credentials not found in environment")
#                 else:
#                     with st.spinner("📡 Connecting to Gmail..."):
#                         try:
#                             state = {}
#                             items_state = fetch_from_gmail(state, download_dir="resumes/gmail")
#                             items = items_state.get("resumes", [])

#                             st.session_state["resume_items"] = items or []
#                             st.session_state["source_type"] = "gmail"
#                             st.success(f"✅ Successfully fetched {len(st.session_state['resume_items'])} resumes!")
#                         except Exception as e:
#                             st.error(f"❌ Error: {e}")

#     elif "Upload Folder" in source:
#         st.markdown("## 📁 Upload Multiple Resumes")
        
#         uploaded_files = st.file_uploader(
#             "Drop resume files here", 
#             accept_multiple_files=True, 
#             type=["pdf", "docx", "doc"],
#             help="Upload multiple resume files at once for batch processing"
#         )
        
#         if st.button("📂 Process Uploaded Files", use_container_width=True):
#             if not uploaded_files:
#                 st.warning("Please upload resume files first")
#             else:
#                 os.makedirs("temp_uploaded", exist_ok=True)
#                 saved_items = []
                
#                 progress_bar = st.progress(0)
#                 for idx, f in enumerate(uploaded_files):
#                     path = os.path.join("temp_uploaded", f.name)
#                     with open(path, "wb") as out:
#                         out.write(f.getbuffer())
#                     saved_items.append({
#                         "filepath": path,
#                         "filename": f.name,
#                         "sender_email": "Uploaded"
#                     })
#                     progress_bar.progress((idx + 1) / len(uploaded_files))
                
#                 st.session_state["resume_items"] = saved_items
#                 st.session_state["source_type"] = "folder"
#                 st.success(f"✅ Successfully uploaded {len(saved_items)} files!")

#     elif "Manual Upload" in source:
#         st.markdown("## 📤 Manual Resume Upload")
        
#         uploaded_files = st.file_uploader(
#             "Upload resumes one by one", 
#             accept_multiple_files=True, 
#             type=["pdf", "docx", "doc"],
#             help="Manually select and upload individual resume files"
#         )
        
#         if st.button("📥 Add to Workspace", use_container_width=True):
#             if uploaded_files:
#                 os.makedirs("temp_manual", exist_ok=True)
#                 current_items = st.session_state.get("resume_items", [])
                
#                 for f in uploaded_files:
#                     path = os.path.join("temp_manual", f.name)
#                     with open(path, "wb") as out:
#                         out.write(f.getbuffer())
#                     current_items.append({
#                         "filepath": path,
#                         "filename": f.name,
#                         "sender_email": "Manual Upload"
#                     })
                
#                 st.session_state["resume_items"] = current_items
#                 st.session_state["source_type"] = "manual"
#                 st.success(f"✅ Added {len(uploaded_files)} resumes to workspace!")

#     elif "Google Drive" in source:
#         st.markdown("## ☁️ Fetch from Google Drive")
#         st.info("📁 Connect to Google Drive using your credentials.json file")
        
#         if st.button("📥 Fetch from Drive", use_container_width=True):
#             with st.spinner("📡 Connecting to Google Drive..."):
#                 try:
#                     initial_state = {
#                         "source_type": "drive",
#                         "jd_text": st.session_state.get("jd_text", ""),
#                         "resume": None
#                     }
                    
#                     state = {} 
#                     items = fetch_from_drive(initial_state)
#                     st.session_state["resume_items"] = items
#                     st.session_state["source_type"] = "drive"
#                     st.success("✅ Successfully fetched resumes from Drive!")
                    
#                 except Exception as e:
#                     st.error(f"❌ Error: {e}")

#     elif "View Results" in source:
#         st.markdown("## 📊 Resume Processing & Results")

#         if st.session_state.get("resume_items"):
#             st.markdown(f"**📁 Workspace:** {len(st.session_state['resume_items'])} resumes loaded")

#             with st.expander("📋 View loaded resumes"):
#                 for i, resume_item in enumerate(st.session_state["resume_items"], start=1):
#                     if isinstance(resume_item, dict):
#                         filepath = resume_item.get("filepath", "")
#                         filename = resume_item.get("filename", os.path.basename(filepath))
#                     else:
#                         filepath = resume_item
#                         filename = os.path.basename(resume_item)
                    
#                     if filepath:
#                         st.markdown(f"**{i}.** `{filename}`")
#                     else:
#                         st.write(f"{i}. ❌ Invalid entry")
#         else:
#             st.info("💡 No resumes in workspace. Load resumes from other tabs first.")

#         st.markdown("<br>", unsafe_allow_html=True)
        
#         # Processing button
#         col1, col2, col3 = st.columns([1, 1, 1])
        
#         with col1:
#             if st.button(
#                 "⚙️ Start Processing", 
#                 disabled=not (st.session_state["resume_items"] and st.session_state["jd_submitted"]),
#                 use_container_width=True
#             ):
#                 if not st.session_state["resume_items"]:
#                     st.error("Please load resumes first")
#                 elif not st.session_state["jd_submitted"]:
#                     st.error("Please submit Job Description first")
#                 else:
#                     with st.spinner("🔄 Processing resumes with AI..."):
#                         progress_bar = st.progress(0)
#                         status_text = st.empty()
                        
#                         try:
#                             source_type = st.session_state.get("source_type", "manual")
#                             results = process_resumes(
#                                 st.session_state["resume_items"], 
#                                 st.session_state["jd_text"],
#                                 source_type
#                             )
                            
#                             st.session_state["results"] = results
#                             st.session_state["processing_complete"] = True
#                             progress_bar.progress(100)
#                             status_text.success(f"✅ Successfully processed {len(results)} resumes!")
                            
#                         except Exception as e:
#                             st.error(f"❌ Processing error: {e}")
        
#         with col2:
#             if st.button("🔄 Clear Results", use_container_width=True):
#                 st.session_state["results"] = []
#                 st.session_state["processing_complete"] = False
#                 st.success("✅ Results cleared!")
#                 st.rerun()
        
#         with col3:
#             if st.button("🗑️ Clear All", use_container_width=True):
#                 st.session_state["resume_items"] = []
#                 st.session_state["results"] = []
#                 st.session_state["jd_text"] = ""
#                 st.session_state["jd_submitted"] = False
#                 st.session_state["processing_complete"] = False
#                 st.success("✅ All data cleared!")
#                 st.rerun()
        
#         st.markdown("---")
        
#         # Display results if available
#         if st.session_state.get("processing_complete") and st.session_state.get("results"):
#             display_results_table(st.session_state["results"])

# if __name__ == "__main__":
#     run_streamlit()



import os
import re
import streamlit as st
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import pandas as pd

# Import your updated functions
from app.utils import rank_top_candidates, fetch_from_gmail, fetch_from_drive 
from app.utils import extract_text_from_pdf, parse_resume
from app.langgraph_flow import graph
from typing import Dict

load_dotenv()

def process_resumes(resume_items, jd_text, source_type="manual"):
    """Process multiple resumes using the LangGraph pipeline"""
    all_results = []

    for i, item in enumerate(resume_items):
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
            resume_text = ""
            if path.lower().endswith('.pdf'):
                resume_text = extract_text_from_pdf(path)
            elif path.lower().endswith(('.docx', '.doc')):
                with open(path, 'r', encoding='utf-8') as f:
                    resume_text = f.read()
            
            if not resume_text.strip():
                st.warning(f"⚠️ Could not extract text from: {filename}")
                continue

            initial_state = {
                "source_type": source_type,
                "jd_text": jd_text,
                "resume": path,
                "resume_text": resume_text,
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
                "rank": 0,
                "address": ""
            }

            parsed_state = parse_resume(initial_state)
            
            st.info(f"🔍 Parsing: {filename}")
            st.info(f"   📝 {parsed_state.get('name', 'Not found')} | 📧 {parsed_state.get('email', 'Not found')}")

            result_state = graph.invoke(parsed_state)

            name = result_state.get("name")
            email = result_state.get("email")
            mobile = result_state.get("mobile")
            address = result_state.get("address")

            score = result_state.get("score", 0)
            feedback = "Accept" if score >= 6.5 else "Reject"

            if result_state.get("experience_filtered", False):
                feedback = "Rejected (Experience)"
                st.info(f"📋 {name}: Filtered out due to insufficient experience")

            analysis = result_state.get("analysis", {})

            result_data = {
                "name": name,
                "email": email,
                "score": score,
                "feedback": feedback,
                "mobile": mobile,
                "address": address,
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
            import traceback
            st.error(traceback.format_exc())
            continue

    return all_results

def load_custom_css():
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');
        
        /* Global Styles */
        .stApp {
            background: linear-gradient(135deg, #56CCF2 0%, #2F80ED 100%);
            font-family: 'Inter', sans-serif;
        }
        
        /* Main container with glass effect */
        .main .block-container {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 2rem 3rem;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
            margin-top: 2rem;
        }
        
        /* Header styling */
        h1 {
            color: black;
            font-weight: 800;
            font-size: 3rem !important;
            margin-bottom: 0.5rem !important;
            letter-spacing: -1px;
        }
        h2 {
            color: #1e293b;
            font-weight: 700;
            font-size: 1.8rem !important;
            margin-top: 2rem !important;
            margin-bottom: 1rem !important;
        }
        
        h3 {
            color: #475569;
            font-weight: 600;
            font-size: 1.2rem !important;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1e293b 0%, #334155 100%);
            border-right: none;
        }
        
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
            color: #e2e8f0;
        }
        
        [data-testid="stSidebar"] .stRadio label {
            color: #e2e8f0 !important;
            font-weight: 500;
            padding: 0.75rem 1rem;
            border-radius: 12px;
            transition: all 0.3s ease;
        }
        
        [data-testid="stSidebar"] .stRadio label:hover {
            background: rgba(255, 255, 255, 0.1);
        }
        
        /* Button styling */
        .stButton > button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 12px;
            padding: 0.75rem 2rem;
            font-weight: 600;
            font-size: 1rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }
        
        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
        }
        
        .stButton > button:active {
            transform: translateY(0);
        }
        
        /* Metric cards */
        [data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 700;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        [data-testid="stMetricLabel"] {
            color: #64748b;
            font-weight: 600;
            font-size: 0.9rem !important;
        }
        
        div[data-testid="metric-container"] {
            background: white;
            padding: 1.5rem;
            border-radius: 16px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e2e8f0;
        }
        
        /* Text area styling */
        .stTextArea textarea {
            border-radius: 12px;
            border: 2px solid #e2e8f0;
            padding: 1rem;
            font-size: 0.95rem;
            transition: all 0.3s ease;
        }
        
        .stTextArea textarea:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        /* File uploader */
        [data-testid="stFileUploader"] {
            background: white;
            border-radius: 16px;
            border: 2px dashed #cbd5e1;
            padding: 2rem;
            transition: all 0.3s ease;
        }
        
        [data-testid="stFileUploader"]:hover {
            border-color: #667eea;
            background: #f8fafc;
        }
        
        /* Expander styling */
        .streamlit-expanderHeader {
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: 1px solid #e2e8f0;
            font-weight: 600;
            color: #1e293b;
        }
        
        .streamlit-expanderHeader:hover {
            border-color: #667eea;
        }
        
        /* Success/Error/Warning messages */
        .stSuccess {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: none;
        }
        
        .stError {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: none;
        }
        
        .stWarning {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: none;
        }
        
        .stInfo {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            border: none;
        }
        
        /* DataTable styling */
        .dataframe {
            border-radius: 12px !important;
            overflow: hidden;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08) !important;
        }
        
        .dataframe thead tr th {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
            color: white !important;
            font-weight: 700 !important;
            padding: 1rem !important;
            border: none !important;
        }
        
        .dataframe tbody tr:hover {
            background: #f8fafc !important;
        }
        
        .dataframe tbody tr td {
            padding: 0.75rem 1rem !important;
            border-bottom: 1px solid #e2e8f0 !important;
        }
        
        /* Score badges in table */
        .score-badge-high {
            background: #d1fae5;
            color: #065f46;
            padding: 0.35rem 0.75rem;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        .score-badge-medium {
            background: #fef3c7;
            color: #92400e;
            padding: 0.35rem 0.75rem;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        .score-badge-low {
            background: #fee2e2;
            color: #991b1b;
            padding: 0.35rem 0.75rem;
            border-radius: 12px;
            font-weight: 600;
            display: inline-block;
        }
        
        /* Skill tags */
        .skill-tag {
            background: linear-gradient(135deg, #e0e7ff 0%, #ddd6fe 100%);
            color: #5b21b6;
            padding: 0.35rem 0.75rem;
            border-radius: 20px;
            margin: 0.15rem;
            display: inline-block;
            font-size: 0.75rem;
            font-weight: 600;
            box-shadow: 0 2px 8px rgba(91, 33, 182, 0.1);
        }
        
        /* Progress bar */
        .stProgress > div > div {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            border-radius: 10px;
        }
        
        /* Divider */
        hr {
            margin: 2rem 0;
            border: none;
            height: 1px;
            background: linear-gradient(90deg, transparent, #e2e8f0, transparent);
        }
        
        /* Cards for candidates */
        .candidate-card {
            background: white;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.08);
            border: 1px solid #e2e8f0;
            transition: all 0.3s ease;
            margin-bottom: 1rem;
        }
        
        .candidate-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(102, 126, 234, 0.15);
        }
        
        /* Badge styles */
        .badge {
            display: inline-block;
            padding: 0.35rem 0.75rem;
            border-radius: 12px;
            font-size: 0.85rem;
            font-weight: 600;
            margin: 0.25rem;
        }
        
        .badge-accept {
            background: #d1fae5;
            color: #065f46;
        }
        
        .badge-reject {
            background: #fee2e2;
            color: #991b1b;
        }
        
        /* Form styling */
        .stForm {
            background: white;
            border-radius: 16px;
            padding: 2rem;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            border: 1px solid #e2e8f0;
        }
        
        /* Download button special styling */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%) !important;
        }
        
        .stDownloadButton > button:hover {
            box-shadow: 0 6px 20px rgba(16, 185, 129, 0.4);
        }
        
        /* Select box styling */
        .stSelectbox > div > div {
            border-radius: 12px;
            border: 2px solid #e2e8f0;
        }
        
        /* Tab styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            border-radius: 12px;
            padding: 0.75rem 1.5rem;
            background: white;
            border: 2px solid #e2e8f0;
            font-weight: 600;
        }
        
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: transparent;
        }
        </style>
    """, unsafe_allow_html=True)

def get_score_badge_html(score):
    """Return HTML badge based on score"""
    if score >= 7:
        return f'<span class="score-badge-high">⭐ {score:.2f}</span>'
    elif score >= 5:
        return f'<span class="score-badge-medium">📊 {score:.2f}</span>'
    else:
        return f'<span class="score-badge-low">📉 {score:.2f}</span>'

def display_results_table(processed_resumes):
    """Display results in a sortable table format"""
    if not processed_resumes:
        st.warning("⚠️ No candidates to display.")
        return

    st.markdown("## 📊 Results Dashboard")
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Total Candidates", len(processed_resumes))
    with col2:
        accepted = len([r for r in processed_resumes if r.get("feedback") == "Accept"])
        st.metric("✅ Accepted", accepted)
    with col3:
        avg_score = sum(r.get("score", 0) for r in processed_resumes) / len(processed_resumes) if processed_resumes else 0
        st.metric("📈 Avg Score", f"{avg_score:.2f}")
    with col4:
        top_score = max(r.get("score", 0) for r in processed_resumes) if processed_resumes else 0
        st.metric("⭐ Top Score", f"{top_score:.2f}")

    st.markdown("<br>", unsafe_allow_html=True)
    
    # Sorting controls
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        sort_column = st.selectbox(
            "📋 Sort by:",
            ["Final Score", "Name", "Email", "Experience", "Similarity Score", "LLM Score", "Embedding Score"],
            index=0
        )
    with col2:
        sort_order = st.selectbox(
            "🔄 Order:",
            ["Descending (High to Low)", "Ascending (Low to High)"],
            index=0
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        view_mode = st.radio("View:", ["Table", "Cards"], horizontal=True)
    
    # Map sort column to data field
    sort_mapping = {
        "Final Score": "score",
        "Name": "name",
        "Email": "email",
        "Experience": "experience",
        "Similarity Score": "similarity_score",
        "LLM Score": "llm_score",
        "Embedding Score": "embedding_score"
    }
    
    sort_field = sort_mapping[sort_column]
    ascending = "Ascending" in sort_order
    
    # Sort the data
    try:
        sorted_resumes = sorted(
            processed_resumes,
            key=lambda x: float(x.get(sort_field, 0)) if sort_field in ["score", "similarity_score", "llm_score", "embedding_score", "experience"] else str(x.get(sort_field, "")),
            reverse=not ascending
        )
    except:
        sorted_resumes = processed_resumes
    
    # Add rank
    for i, res in enumerate(sorted_resumes, 1):
        res["rank"] = i
    
    if view_mode == "Table":
        # Table View
        st.markdown("### 📋 Candidate Results Table")
        
        # Prepare data for table
        table_data = []
        for res in sorted_resumes:
            name = res.get('name', 'N/A') or f"Candidate_{res.get('rank', '?')}"
            table_data.append({
                "Rank": res.get("rank", "-"),
                "Name": name,
                "Email": res.get("email", "N/A") or "N/A",
                "Mobile": res.get("mobile", "N/A") or "N/A",
                "Score": round(res.get("score", 0), 2),
                "Feedback": res.get("feedback", "N/A"),
                "Experience": res.get("experience", "0"),
                "Education": res.get("education", "Unknown"),
                "Job Type": res.get("job_type", "Unknown"),
            })
        
        # Create DataFrame
        df = pd.DataFrame(table_data)
        
        # Display table with custom styling
        st.dataframe(
            df,
            use_container_width=True,
            height=600,
            hide_index=True,
            column_config={
                "Rank": st.column_config.NumberColumn("🏅 Rank", width="small"),
                "Name": st.column_config.TextColumn("👤 Name", width="medium"),
                "Email": st.column_config.TextColumn("📧 Email", width="medium"),
                "Mobile": st.column_config.TextColumn("📱 Mobile", width="medium"),
                "Score": st.column_config.NumberColumn("⭐ Score", format="%.2f", width="small"),
                "Feedback": st.column_config.TextColumn("✅ Status", width="small"),
                "Experience": st.column_config.TextColumn("💼 Exp (yrs)", width="small"),
                "Education": st.column_config.TextColumn("🎓 Education", width="medium"),
                "Job Type": st.column_config.TextColumn("💼 Job Type", width="medium"),
            }
        )
        
        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv,
            file_name=f"candidate_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        # Card View
        st.markdown("### 🎴 Candidate Cards")
        
        for res in sorted_resumes[:20]:  # Show top 20 in card view
            score = res.get('score', 0)
            
            candidate_name = res.get('name', 'N/A')
            if not candidate_name or candidate_name == "None":
                candidate_name = f"Candidate_{res.get('rank', '?')}"
            
            with st.expander(f"🏅 Rank {res.get('rank', '?')}: {candidate_name} · Score: {score:.2f}", expanded=False):
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.markdown("#### 👤 Profile")
                    st.markdown(f"**Name:** {res.get('name', 'N/A') or 'N/A'}")
                    st.markdown(f"**📧 Email:** {res.get('email', 'N/A') or 'N/A'}")
                    st.markdown(f"**📱 Mobile:** {res.get('mobile', 'N/A') or 'N/A'}")
                    st.markdown(f"**📍 Location:** {res.get('address', 'Unknown') or 'Unknown'}")
                    st.markdown(f"**💼 Job Type:** {res.get('job_type', 'Unknown') or 'Unknown'}")
                    
                    feedback = res.get('feedback', 'No feedback')
                    if feedback == "Accept":
                        st.markdown(f"<div class='badge badge-accept'>✅ {feedback}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div class='badge badge-reject'>❌ {feedback}</div>", unsafe_allow_html=True)
                
                with col2:
                    st.markdown("#### 📊 Scores & Analysis")
                    st.markdown(f"**Final Score:** {get_score_badge_html(score)}", unsafe_allow_html=True)
                    st.markdown(f"**🎯 Similarity Score:** {res.get('similarity_score', 'N/A')}")
                    st.markdown(f"**🤖 LLM Score:** {res.get('llm_score', 'N/A')}")
                    st.markdown(f"**📊 Embedding Score:** {res.get('embedding_score', 'N/A')}")
                    st.markdown(f"**🎓 Education:** {res.get('education', 'Unknown')}")
                    st.markdown(f"**💼 Experience:** {res.get('experience', '0')} years")
                
                # Skills section
                skills = res.get('skills', [])
                if skills and isinstance(skills, list):
                    st.markdown("#### 🔧 Skills")
                    skills_html = " ".join([f"<span class='skill-tag'>{skill}</span>" for skill in skills[:15]])
                    st.markdown(skills_html, unsafe_allow_html=True)
                
                # Resume file info
                resume_path = res.get("resume_path") or res.get("filepath")
                if resume_path and os.path.exists(resume_path):
                    st.markdown(f"<br>📄 **Resume:** `{os.path.basename(resume_path)}`", unsafe_allow_html=True)

def run_streamlit():
    st.set_page_config(
        page_title="HR Hiring Bot - AI Powered",
        page_icon="🤖",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    load_custom_css()

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
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("<h1>🤖 HR Hiring Bot</h1>", unsafe_allow_html=True)
        st.markdown("**AI-Powered Resume Screening with LangGraph Intelligence**")

    # Sidebar navigation
    with st.sidebar:
        st.markdown("### 🎯 Navigation")
        source = st.radio(
            "",
            ["📩 Gmail", "📁 Upload Folder", "📤 Manual Upload", "☁️ Google Drive", "📊 View Results"],
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.markdown("### 📈 Quick Stats")
        if st.session_state.get("resume_items"):
            st.info(f"📁 **Loaded:** {len(st.session_state['resume_items'])} resumes")
        if st.session_state.get("results"):
            st.success(f"✅ **Processed:** {len(st.session_state['results'])} candidates")

    # Job Description section
    st.markdown("## 📄 Job Description")
    
    jd_col1, jd_col2 = st.columns([5, 1])
    
    with jd_col1:
        jd_text_input = st.text_area(
            "Paste Job Description", 
            height=200, 
            value=st.session_state["jd_text"],
            placeholder="📝 Enter the complete job description for AI-powered candidate matching...",
            help="Provide a detailed job description for better matching accuracy"
        )
        jd_file = st.file_uploader("📎 Or upload JD file (optional)", type=["txt", "pdf"])
    
    with jd_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Submit JD", use_container_width=True):
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
                        st.error(f"Error extracting text: {e}")
                else:
                    try:
                        final_jd_text = jd_file.read().decode("utf-8")
                    except Exception:
                        st.error("Error reading file")
            else:
                final_jd_text = jd_text_input

            if final_jd_text and final_jd_text.strip():
                st.session_state["jd_text"] = final_jd_text
                st.session_state["jd_submitted"] = True
                st.success("✅ Job Description submitted successfully!")
            else:
                st.warning("⚠️ Please provide a valid Job Description.")

    # Status indicator
    if st.session_state["jd_submitted"]:
        st.success("✅ Job Description is ready for processing")
    else:
        st.info("💡 Submit a Job Description to enable resume processing")

    st.markdown("---")

    # Source-specific sections
    if "Gmail" in source:
        st.markdown("## 📩 Fetch Resumes from Gmail")
        
        with st.form("gmail_form"):
            st.info("📬 Connect to your Gmail account to fetch resumes automatically")
            submitted = st.form_submit_button("📥 Fetch Resumes from Gmail", use_container_width=True)
            
            if submitted:
                user = os.getenv("GMAIL_USER")
                pwd = os.getenv("GMAIL_PASS")
                
                if not user or not pwd:
                    st.error("❌ Gmail credentials not found in environment")
                else:
                    with st.spinner("📡 Connecting to Gmail..."):
                        try:
                            state = {}
                            items_state = fetch_from_gmail(state, download_dir="resumes/gmail")
                            items = items_state.get("resumes", [])

                            st.session_state["resume_items"] = items or []
                            st.session_state["source_type"] = "gmail"
                            st.success(f"✅ Successfully fetched {len(st.session_state['resume_items'])} resumes!")
                        except Exception as e:
                            st.error(f"❌ Error: {e}")

    elif "Upload Folder" in source:
        st.markdown("## 📁 Upload Multiple Resumes")
        
        uploaded_files = st.file_uploader(
            "Drop resume files here", 
            accept_multiple_files=True, 
            type=["pdf", "docx", "doc"],
            help="Upload multiple resume files at once for batch processing"
        )
        
        if st.button("📂 Process Uploaded Files", use_container_width=True):
            if not uploaded_files:
                st.warning("Please upload resume files first")
            else:
                os.makedirs("temp_uploaded", exist_ok=True)
                saved_items = []
                
                progress_bar = st.progress(0)
                for idx, f in enumerate(uploaded_files):
                    path = os.path.join("temp_uploaded", f.name)
                    with open(path, "wb") as out:
                        out.write(f.getbuffer())
                    saved_items.append({
                        "filepath": path,
                        "filename": f.name,
                        "sender_email": "Uploaded"
                    })
                    progress_bar.progress((idx + 1) / len(uploaded_files))
                
                st.session_state["resume_items"] = saved_items
                st.session_state["source_type"] = "folder"
                st.success(f"✅ Successfully uploaded {len(saved_items)} files!")

    elif "Manual Upload" in source:
        st.markdown("## 📤 Manual Resume Upload")
        
        uploaded_files = st.file_uploader(
            "Upload resumes one by one", 
            accept_multiple_files=True, 
            type=["pdf", "docx", "doc"],
            help="Manually select and upload individual resume files"
        )
        
        if st.button("📥 Add to Workspace", use_container_width=True):
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
                st.success(f"✅ Added {len(uploaded_files)} resumes to workspace!")

    elif "Google Drive" in source:
        st.markdown("## ☁️ Fetch from Google Drive")
        st.info("📁 Connect to Google Drive using your credentials.json file")
        
        if st.button("📥 Fetch from Drive", use_container_width=True):
            with st.spinner("📡 Connecting to Google Drive..."):
                try:
                    initial_state = {
                        "source_type": "drive",
                        "jd_text": st.session_state.get("jd_text", ""),
                        "resume": None
                    }
                    
                    state = {} 
                    items = fetch_from_drive(initial_state)
                    st.session_state["resume_items"] = items
                    st.session_state["source_type"] = "drive"
                    st.success("✅ Successfully fetched resumes from Drive!")
                    
                except Exception as e:
                    st.error(f"❌ Error: {e}")

    elif "View Results" in source:
        st.markdown("## 📊 Resume Processing & Results")

        if st.session_state.get("resume_items"):
            st.markdown(f"**📁 Workspace:** {len(st.session_state['resume_items'])} resumes loaded")

            with st.expander("📋 View loaded resumes"):
                for i, resume_item in enumerate(st.session_state["resume_items"], start=1):
                    if isinstance(resume_item, dict):
                        filepath = resume_item.get("filepath", "")
                        filename = resume_item.get("filename", os.path.basename(filepath))
                    else:
                        filepath = resume_item
                        filename = os.path.basename(resume_item)
                    
                    if filepath:
                        st.markdown(f"**{i}.** `{filename}`")
                    else:
                        st.write(f"{i}. ❌ Invalid entry")
        else:
            st.info("💡 No resumes in workspace. Load resumes from other tabs first.")

        st.markdown("<br>", unsafe_allow_html=True)
        
        # Processing button
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            if st.button(
                "⚙️ Start Processing", 
                disabled=not (st.session_state["resume_items"] and st.session_state["jd_submitted"]),
                use_container_width=True
            ):
                if not st.session_state["resume_items"]:
                    st.error("Please load resumes first")
                elif not st.session_state["jd_submitted"]:
                    st.error("Please submit Job Description first")
                else:
                    with st.spinner("🔄 Processing resumes with AI..."):
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
                            status_text.success(f"✅ Successfully processed {len(results)} resumes!")
                            
                        except Exception as e:
                            st.error(f"❌ Processing error: {e}")
        
        with col2:
            if st.button("🔄 Clear Results", use_container_width=True):
                st.session_state["results"] = []
                st.session_state["processing_complete"] = False
                st.success("✅ Results cleared!")
                st.rerun()
        
        with col3:
            if st.button("🗑️ Clear All", use_container_width=True):
                st.session_state["resume_items"] = []
                st.session_state["results"] = []
                st.session_state["jd_text"] = ""
                st.session_state["jd_submitted"] = False
                st.session_state["processing_complete"] = False
                st.success("✅ All data cleared!")
                st.rerun()
        
        st.markdown("---")
        
        # Display results if available
        if st.session_state.get("processing_complete") and st.session_state.get("results"):
            display_results_table(st.session_state["results"])

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
