import os
import re
import json
import ast
from typing import Dict
from langchain_core.prompts import PromptTemplate
from .config import llm
from .core import extract_text_from_pdf, extract_text_with_ocr, clean_text
from .shared_types import ResumeState

def parse_resume(state: Dict) -> Dict:
    """
    Extracts and cleans text from a resume PDF, and uses Groq LLM to extract candidate information.
    """
    resume_path = state.get("resume")
    print(f"🔄 Parsing resume: {resume_path}...")
    if not resume_path or not os.path.exists(resume_path):
        print("❌ Resume file not found")
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found", "address": "Not found", "requires_ocr": False}

    def extract_info_with_groq_llm(text: str) -> Dict[str, str]:
        extraction_prompt = f"""
Please extract the following information from this resume text. If any information is not found, return "Not found" for that field.

Resume Text:
{text[:3000]}

Please extract and return ONLY the following information in this exact JSON format:
{{
    "name": "candidate's full name",
    "email": "email address", 
    "mobile": "phone/mobile number (preferably in +91 format if Indian number)",
    "address": "complete address or location"
}}

Rules:
- For name: Extract the candidate's full name (usually at the top of resume)
- For email: Extract valid email address
- For mobile: Extract phone number, format as +91 XXXXXXXXXX if Indian number  
- For address: Extract complete address or at least city/location  
- Return "Not found" if information is not available
- Return only the JSON, no other text
"""
        try:
            response = llm.invoke(extraction_prompt)
            llm_response = response.content.strip()
            
            json_start = llm_response.find('{')
            json_end = llm_response.rfind('}') + 1
            if json_start != -1 and json_end != 0:
                return json.loads(llm_response[json_start:json_end])
            return {}
        except Exception as e:
            print(f"❌ Error calling Groq LLM: {e}")
            return {}

    # RegEx fallbacks
    def extract_email_regex(text: str) -> str:
        pattern = r'\b[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        matches = re.findall(pattern, text)
        return matches[0] if matches else "Not found"

    def extract_mobile_regex(text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        patterns = [r"\+91\s*([6-9]\d{9})", r"\b([6-9]\d{9})\b"]
        for p in patterns:
            match = re.search(p, text)
            if match: return f"+91 {match.group(1) if len(match.groups())==1 else match.group(0)}"
        return "Not found"

    def extract_name_regex(text: str) -> str:
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        for line in lines[:5]:
            if len(line.split()) >= 2 and not any(kw in line.lower() for kw in ["email", "phone", "resume"]):
                 return line
        return "Not found"

    # Extraction flow
    if resume_path.lower().endswith('.pdf'):
        raw_text, requires_ocr = extract_text_from_pdf(resume_path)
        if requires_ocr:
            raw_text = extract_text_with_ocr(resume_path)
    elif resume_path.lower().endswith(('.docx', '.doc')):
        # Simplified for brevity, usually needs docx2txt
        import docx2txt
        raw_text = docx2txt.process(resume_path)
    else:
        raw_text = ""
        
    cleaned_text = clean_text(raw_text)
    extracted_info = extract_info_with_groq_llm(raw_text)

    name = extracted_info.get("name", extract_name_regex(raw_text))
    email = extracted_info.get("email", extract_email_regex(raw_text))
    mobile = extracted_info.get("mobile", extract_mobile_regex(raw_text))
    address = extracted_info.get("address", "Not found")

    return {**state, "resume_text": cleaned_text, "mobile": mobile, "email": email, "name": name, "address": address}

def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """Extract skills, education, and experience using LLM."""
    print("🔄 Analyzing skills, education, and experience...")
    import ast
    from datetime import datetime

    resume_text = state.get("resume_text", "")
    if not resume_text.strip():
        return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}

    today_date = datetime.now().strftime("%B %d, %Y")  # e.g. "March 10, 2026"

    prompt = PromptTemplate.from_template("""
You are an information extraction system.
TODAY'S DATE IS: {today_date}

Your task is to read the resume text and extract exactly this data:
- Top 10 relevant skills (list of strings)
- Education level (string)
- total_experience_years: Total professional work experience in years (string, e.g., "2", "3.5", "0")

CRITICAL RULES for total_experience_years:
1. Find ALL work experiences, internships, and professional roles listed in the resume.
2. For EACH experience entry, calculate duration:
   - If it says "Present", "Current", "Till Date", or "Ongoing", use TODAY'S DATE ({today_date}) as the end date.
   - Calculate: (end_date - start_date) in years with one decimal place.
   - Example: "March 2024 – Present" with today being {today_date} = approximately 2.0 years.
3. SUM the durations of ALL experience entries together.
   - Example: If a candidate has 3 experiences: 1.5 years + 0.8 years + 0.5 years = "2.8"
4. If duration is in months, convert to years: e.g., "5 months" = "0.4".
5. Do NOT return only the most recent experience. You MUST sum ALL of them.
6. Do NOT infer experience from skills or education. Only count explicitly stated work periods.
7. If no explicit duration or dates are mentioned, return "0".
8. Never round up — keep the exact lower bound with one decimal place.

You must respond with **only valid JSON**. No explanation. No extra words.
If a field is missing in the resume, use defaults: [] for skills, "Unknown" for education, "0" for experience.

Resume:
{resume}

JSON response format (strictly follow this):
{{
  "skills": ["Python", "TensorFlow", "..."],
  "education": "Bachelor of Pharmacy",
  "experience": "2.8"
}}
""")

    try:
        chain = prompt | llm
        response = chain.invoke({"resume": resume_text, "today_date": today_date})
        raw_response = response.content.strip()
        # print("✅ LLM raw response:\n", raw_response)

        raw_response = re.sub(r"```(json)?", "", raw_response).strip()

        if "{" in raw_response and "}" in raw_response:
            start_idx = raw_response.find("{")
            end_idx = raw_response.rfind("}") + 1
            json_str = raw_response[start_idx:end_idx]
        else:
            json_str = raw_response

        analysis = None
        try:
            analysis = json.loads(json_str)
        except json.JSONDecodeError:
            try:
                analysis = ast.literal_eval(json_str)
            except Exception:
                analysis = {"skills": [], "education": "Unknown", "experience": "0"}

        if analysis:
            analysis.setdefault("skills", [])
            analysis.setdefault("education", "Unknown")
            analysis.setdefault("experience", "0")
            if not isinstance(analysis["skills"], list):
                analysis["skills"] = []
        else:
            analysis = {"skills": [], "education": "Unknown", "experience": "0"}

        print("✅ Final parsed analysis:\n", analysis)
        return {**state, "analysis": analysis}

    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()
        return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}

def compute_similarity(state: ResumeState) -> ResumeState:
    """Compute combined LLM and Embedding similarity."""
    print("🔄 Computing similarity score against Job Description...")
    jd, resume = state.get("jd_text", ""), state.get("resume_text", "")
    if not jd or not resume: return {**state, "similarity_score": 0}

    # Simplified embedding for brevity
    from sklearn.metrics.pairwise import cosine_similarity
    from langchain_community.embeddings import HuggingFaceEmbeddings
    
    embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    jd_vec, res_vec = embed.embed_query(jd), embed.embed_query(resume)
    embed_score = round(float(cosine_similarity([jd_vec], [res_vec])[0][0]) * 10, 2)

    prompt = PromptTemplate.from_template("Score resume vs JD (0-10). JD: {jd} Resume: {resume}. Return number only.")
    resp = llm.invoke(prompt.format(jd=jd, resume=resume))
    try: llm_score = float(re.findall(r'\d+\.?\d*', resp.content)[0])
    except: llm_score = 0

    combined = round(0.6 * llm_score + 0.4 * embed_score, 2)
    return {**state, "llm_score": llm_score, "embedding_score": embed_score, "similarity_score": combined}

def classify_resume(state: ResumeState) -> ResumeState:
    """Classify into job categories."""
    print("🔄 Classifying resume into job categories...")
    # prompt = PromptTemplate.from_template("Classify resume into category. Categories: AI Engineer, Data Analyst, etc. JD: {jd} Resume: {resume}. Return category name only.")
    prompt = PromptTemplate.from_template("""
        You are an expert HR recruiter classifying resumes based on job descriptions.
        
        Task: Classify the candidate's Resume into one of the exact Job Categories listed below based on their skills and experience.
        If the Resume does NOT match the Job Description or does not fit any of the listed categories well, you MUST output "N/A".

        Job Categories List:
        - AI Engineer
        - Data Analyst
        - Machine Learning Engineer
        - Data Annotator
        - UI/UX Designer
        - Backend Developer
        - Frontend Developer
        - Full Stack Developer
        - DevOps Engineer
        - Hr Executive
        - Hr intern 
        - bussiness development intern
        - bussiness Analyst
        - bussiness analyst intern

        Job Description:
        {jd}

        Resume:
        {resume}

        Instructions:
        1. Only return the exact name of the job category from the list above.
        2. Do not include any explanations, punctuation, or other text.
        3. If the resume is completely unrelated to the job description, return "N/A".
        """)
    resp = llm.invoke(prompt.format(jd=state.get("jd_text", ""), resume=state.get("resume_text", "")))
    return {**state, "job_type": resp.content.strip()}

def score_resume(state: ResumeState) -> ResumeState:
    """Calculate final weighted score and filter by experience."""
    print("🔄 Calculating final resume score...")
    MIN_SIMILARITY_THRESHOLD = 5
    
    def extract_required_experience(jd_text):
        match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
        return int(match.group(1)) if match else None
    
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})

    if similarity < MIN_SIMILARITY_THRESHOLD:
        return {**state, "score": 0, "experience_filtered": False}
    
    req_exp = extract_required_experience(state.get("jd_text", ""))
    try:
        candidate_exp = float(analysis.get("experience", 0))
    except (ValueError, TypeError):
        candidate_exp = 0.0

    if req_exp is not None and candidate_exp < req_exp:
        print(f"❌ Rejected: Needs {req_exp}+ years, has {candidate_exp} years")
        return {**state, "score": 0, "experience_filtered": True}

    return {**state, "score": similarity, "experience_filtered": False}

def save_to_db_node(state: ResumeState) -> ResumeState:
    """Save processed data to DB."""
    print(f"🔄 Saving candidate {state.get('name', 'Unknown')} to database...")
    from app.database import get_db
    from app.crud import create_or_update_candidate, save_resume_analysis, create_job_description
    db = next(get_db())
    try:
        cand = create_or_update_candidate(db, {"name": state.get("name"), "email": state.get("email"), "mobile": state.get("mobile"), "address": state.get("address"), "skills": state.get("analysis", {}).get("skills", []), "education": state.get("analysis", {}).get("education", "Unknown"), "experience": state.get("analysis", {}).get("experience", "0")})
        job = create_job_description(db, state.get("job_type", "General"), state.get("jd_text", ""))
        save_resume_analysis(db=db, candidate_id=cand.id, file_path=state.get("resume", "N/A"), source=state.get("source_type", "unknown"), result_state=state, job_id=job.id)
    finally:
        db.close()
    return state

def rank_top_candidates(processed_resumes):
    """Rank candidates based on their scores"""
    print(f"🔄 Ranking top candidates from a pool of {len(processed_resumes)} resumes...")
    scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]
    scored_resumes.sort(key=lambda x: x["score"], reverse=True) 

    for i, res in enumerate(scored_resumes, 1):
        res["rank"] = i

    return scored_resumes[:10]
