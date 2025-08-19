import mimetypes
from pathlib import Path
import os
import re
import pdfplumber
import imaplib
import email
from datetime import datetime, timedelta
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from sklearn.metrics.pairwise import cosine_similarity
import json
from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
import pandas as pd
import gspread
import requests
from google.oauth2 import service_account
import requests
from langchain.embeddings import HuggingFaceEmbeddings
from typing import TypedDict
from typing import List, Dict
# Load environment variables
load_dotenv()
llm = ChatGroq(model="llama3-8b-8192", api_key=os.getenv("GROQ_API_KEY"))


# =============================================================================
# 1. SOURCE SELECTION AND FETCHING FUNCTIONS
# =============================================================================

from app.shared_types import ResumeState 
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.langgraph_flow import ResumeState
def choose_source(state: ResumeState) -> ResumeState:   #first state where user can choose source of resume doucement 
    """
    Entry point - determines which source to use for fetching resumes
    This should be configured based on your needs
    """
    # For now, defaulting to folder source - modify as needed
    source_type = state.get("source_type", "folder")
    print(f"✅ Chosen source: {source_type}")
    return {**state, "source_type": source_type}



def fetch_resumes_from_gmail(user_email: str, app_password: str, download_dir: str = "resumes/gmail") -> list[dict]:
    """
    Fetch resumes (PDF/DOC/DOCX) from Gmail inbox in the last 20 days.
    """
    os.makedirs(download_dir, exist_ok=True)
    allowed_ext = (".pdf", ".doc", ".docx")
    downloaded = []

    try:
        # Connect to Gmail
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        date_since = (datetime.now() - timedelta(days=20)).strftime("%d-%b-%Y")
        result, data = mail.search(None, f'(SINCE {date_since})')

        if result != "OK":
            print("❌ Error searching mailbox")
            return []

        for eid in data[0].split():
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            subject = msg.get("subject", "").lower()

            if not any(kw in subject for kw in ["resume", "job", "application"]):
                continue

            sender_email = msg.get("From")

            for part in msg.walk():
                if part.get("Content-Disposition") and "attachment" in part.get("Content-Disposition"):
                    filename = part.get_filename()
                    if filename and filename.lower().endswith(allowed_ext):
                        filepath = os.path.join(download_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(part.get_payload(decode=True))
                        downloaded.append({
                            "filepath": filepath,
                            "sender_email": sender_email
                        })

        # mail.logout()
        return downloaded

    except Exception as e:
        print(f"❌ Error fetching resumes from Gmail: {e}")
        return []


def fetch_from_gmail(state: dict, download_dir: str = "resumes/gmail") -> dict:
    """
    Wrapper to integrate Gmail fetch into ResumeState workflow.
    """
    user_email = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_PASS")

    if not user_email or not app_password:
        print("❌ Gmail credentials not found in environment variables.")
        return {**state, "resumes": []}

    downloaded = fetch_resumes_from_gmail(user_email, app_password, download_dir)

    if downloaded:
        print(f"✅ Successfully fetched {len(downloaded)} resumes from Gmail.")
        return {**state, "resumes": downloaded}
    else:
        print("❌ No resumes found in Gmail in the last 7 days.")
        return {**state, "resumes": []}




import pandas as pd
import gspread
import requests
import os
import re
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from pathlib import Path





def fetch_from_drive(state=None):
    """
    Fetch resumes from Google Drive via Google Sheets using Drive API.
    """
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    def get_file_id(drive_url: str) -> str:
        """Extract file ID from Google Drive URL."""
        if "id=" in drive_url:
            return drive_url.split("id=")[1]
        elif "/d/" in drive_url:
            return drive_url.split("/d/")[1].split("/")[0]
        return None

    try:
        # ✅ Authenticate with Service Account
        creds = service_account.Credentials.from_service_account_file(
            r'D:\hr_chatboat\credentials.json',
            scopes=SCOPES
        )

        # ✅ Read Google Sheet
        gc = gspread.authorize(creds)
        SHEET_ID = '12iGOUPpqLHi-olf7qfiTm4I-ZCEaLpzpfB0WCvaTSRw'
        sh = gc.open_by_key(SHEET_ID)
        print(f"sheeet {sh}")
        ws = sh.sheet1
        print(f"sheeet 1 {sh}")
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)
        print(f"data fareme {df.columns}")
        print({SHEET_ID})

        resume_links = df["Resume"].dropna().tolist()
        print("📄 Resume links found:", resume_links)

        # ✅ Prepare Drive API
        drive_service = build("drive", "v3", credentials=creds)
        os.makedirs("resumes/from_drive", exist_ok=True)

        downloaded_resumes = []
        for link in resume_links:
            file_id = get_file_id(link)
            if not file_id:
                print(f"❌ Could not extract file_id from: {link}")
                continue

            try:
                # ✅ Step 1: Get metadata (original file name + type)
                meta = drive_service.files().get(
                    fileId=file_id,
                    fields="name,mimeType"
                ).execute()
                print({meta})

                orig_name = meta.get("name", f"{file_id}.pdf")  # fallback if no name
                mime_type = meta.get("mimeType")

                # ✅ Step 2: Prepare download request
                request = drive_service.files().get_media(fileId=file_id)

                # ✅ Step 3: Download file
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()

                fh.seek(0)

                # ✅ Step 4: Save using original filename
                file_path = Path("resumes/from_drive") / orig_name
                with open(file_path, "wb") as f:
                    f.write(fh.read())

                print(f"✅ Saved with original name: {file_path}")
                downloaded_resumes.append(str(file_path))

            except Exception as e:
                print(f"❌ Failed to download {link}: {e}")

        return downloaded_resumes

    except Exception as e:
        print(f"❌ Error in fetch_from_drive: {e}")
        return []

                                                                                                                                                           
        

def fetch_from_folder(state: ResumeState) -> ResumeState:
    """
    Fetch resumes from local folder
    """
    folder_path = "resumes/local"  # Adjust path as needed
    
    if not os.path.exists(folder_path):
        print(f"❌ Folder {folder_path} does not exist")
        return {**state, "resume": None}
    
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if pdf_files:
        resume_path = os.path.join(folder_path, pdf_files[0])
        print(f"✅ Fetched resume from folder: {resume_path}")
        return {**state, "resume": resume_path}
    else:
        print("❌ No PDF files found in folder")
        return {**state, "resume": None}

def manual_upload(state: ResumeState) -> ResumeState:
    """
    Handle manual file upload (placeholder for web interface)
    """
    # This would be implemented in your web interface
    print("✅ Manual upload selected")
    return state

# =============================================================================
# 2. RESUME PROCESSING FUNCTIONS
# =============================================================================

import os
import re
import pdfplumber
from typing import Dict  # Adjust if you have a custom ResumeState type


# ✅ Reusable function (can be imported anywhere)
def extract_text_from_pdf(filepath: str) -> str:
    """
    Extracts text from a PDF file using pdfplumber.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with pdfplumber.open(filepath) as pdf:
        text = "\n".join(
            [page.extract_text() for page in pdf.pages if page.extract_text()]
        )
    return text











import os
import re
import json
import pdfplumber
from typing import Dict
from langchain_groq import ChatGroq

def extract_text_from_pdf(filepath: str) -> str:
    """
    Extracts text from a PDF file using pdfplumber.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    with pdfplumber.open(filepath) as pdf:
        text = "\n".join(
            [page.extract_text() for page in pdf.pages if page.extract_text()]
        )
    return text

def parse_resume(state: Dict) -> Dict:
    """
    Extracts and cleans text from a resume PDF, and uses Groq Llama3 to extract candidate information.
    Falls back to regex-based extraction if LLM fails.
    """
    resume_path = state.get("resume")

    if not resume_path or not os.path.exists(resume_path):
        print("❌ Resume file not found")
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found", "address": "Not found"}

    def clean_text(text: str) -> str:
        # Clean each line separately to preserve line structure
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove extra whitespaces within each line but preserve line breaks
            line = re.sub(r"[ \t]+", " ", line)  # Only collapse spaces and tabs, not newlines
            line = re.sub(r"[^\x00-\x7F]+", " ", line)  # Remove non-ASCII characters
            line = line.strip()  # Remove leading/trailing whitespace from each line
            if line:  # Only add non-empty lines
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)

    def extract_info_with_groq_llm(text: str) -> Dict[str, str]:
        """
        Use Groq Llama3 to extract candidate information from resume text.
        Returns a dictionary with name, email, mobile, and address.
        """
        
        # Create a structured prompt for the LLM
        extraction_prompt = f"""
Please extract the following information from this resume text. If any information is not found, return "Not found" for that field.

Resume Text:
{text[:3000]}  # Limit text to avoid token limits

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
            print("🤖 Using Groq Llama3 to extract candidate information...")
            
            # Initialize Groq LLM (using your existing setup)
            llm = ChatGroq(
                model="llama3-8b-8192", 
                api_key=os.getenv("GROQ_API_KEY"),
                temperature=0  # For consistent extraction
            )
            
            # Call the LLM
            response = llm.invoke(extraction_prompt)
            llm_response = response.content
            
            print(f"🔍 LLM Raw Response: {llm_response[:200]}...")  # Debug output
            
            # Parse the JSON response
            try:
                # Clean the response to extract JSON
                llm_response = llm_response.strip()
                
                # Find JSON in the response
                json_start = llm_response.find('{')
                json_end = llm_response.rfind('}') + 1
                
                if json_start != -1 and json_end != 0:
                    json_str = llm_response[json_start:json_end]
                    extracted_info = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No JSON found", llm_response, 0)
                    
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON parsing failed: {e}")
                print(f"⚠️  Raw LLM response: {llm_response}")
                
                # If LLM doesn't return valid JSON, try to extract from text
                extracted_info = {
                    "name": "Not found",
                    "email": "Not found",
                    "mobile": "Not found", 
                    "address": "Not found"
                }
                
                # Basic fallback parsing if JSON fails
                lines = llm_response.split('\n')
                for line in lines:
                    line = line.strip()
                    if any(keyword in line.lower() for keyword in ['name:', 'name":', '"name"']):
                        # Extract value after colon
                        if ':' in line:
                            value = line.split(':')[1].strip().strip('"\'').strip(',')
                            if value and value.lower() not in ['not found', '', 'none', 'null', 'n/a']:
                                extracted_info['name'] = value
                    
                    elif any(keyword in line.lower() for keyword in ['email:', 'email":', '"email"']):
                        if ':' in line:
                            value = line.split(':')[1].strip().strip('"\'').strip(',')
                            if value and value.lower() not in ['not found', '', 'none', 'null', 'n/a']:
                                extracted_info['email'] = value
                    
                    elif any(keyword in line.lower() for keyword in ['mobile:', 'mobile":', '"mobile"', 'phone:']):
                        if ':' in line:
                            value = line.split(':')[1].strip().strip('"\'').strip(',')
                            if value and value.lower() not in ['not found', '', 'none', 'null', 'n/a']:
                                extracted_info['mobile'] = value
                    
                    elif any(keyword in line.lower() for keyword in ['address:', 'address":', '"address"']):
                        if ':' in line:
                            value = line.split(':')[1].strip().strip('"\'').strip(',')
                            if value and value.lower() not in ['not found', '', 'none', 'null', 'n/a']:
                                extracted_info['address'] = value
            
            # Validate and clean extracted information
            for key, value in extracted_info.items():
                if isinstance(value, str):
                    value = value.strip().strip('"\'').strip(',')
                    if value.lower() in ['not found', '', 'none', 'null', 'n/a']:
                        extracted_info[key] = "Not found"
                    else:
                        extracted_info[key] = value
                else:
                    extracted_info[key] = "Not found"
            
            print(f"✅ Groq LLM extraction completed:")
            print(f"   Name: {extracted_info.get('name', 'Not found')}")
            print(f"   Email: {extracted_info.get('email', 'Not found')}")
            print(f"   Mobile: {extracted_info.get('mobile', 'Not found')}")
            print(f"   Address: {extracted_info.get('address', 'Not found')}")
            
            return extracted_info
            
        except Exception as e:
            print(f"❌ Error calling Groq LLM: {e}")
            # Return default values if LLM call fails
            return {
                "name": "Not found",
                "email": "Not found",
                "mobile": "Not found",
                "address": "Not found"
            }

    # Fallback regex functions (your original functions for backup)
    def extract_email_regex(text: str) -> str:
        """Fallback email extraction using regex"""
        standard_email_pattern = r'\b[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        standard_matches = re.findall(standard_email_pattern, text)
        for email in standard_matches:
            if re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return email
        return "Not found"

    def extract_mobile_regex(text: str) -> str:
        """Improved fallback mobile extraction using regex"""
        text = re.sub(r'\s+', ' ', text)
        patterns = [
            # Match +91 876 7357785 format (with spaces) 
            r"\+91\s*([6-9]\d{2})\s*([0-9]\d{2})\s*([0-9]\d{2}\d{1})",
            # Match +91 8767357785 format (no spaces)
            r"\+91\s*([6-9]\d{9})",
            # Match 91 8767357785 format
            r"\b91\s*([6-9]\d{9})",
            # Match standalone 10-digit numbers
            r"\b([6-9]\d{9})\b",
            # Match with Phone/Mobile labels
            r"(?:Phone|Mobile|Contact|Ph)[\s:]*\+?91[\s-]*([6-9]\d{9})",
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                if len(match.groups()) == 1:
                    # Single group - full number
                    number = match.group(1)
                elif len(match.groups()) == 3:
                    # Three groups - combine them
                    number = match.group(1) + match.group(2) + match.group(3)
                else:
                    number = match.group(0)
                
                # Clean and validate
                clean_number = re.sub(r"[^\d]", "", number)
                if len(clean_number) == 10 and clean_number[0] in "6789":
                    return f"+91 {clean_number}"
        return "Not found"

    def extract_name_regex(text: str) -> str:
        """Fallback name extraction using regex"""
        lines = text.strip().split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        
        exclusion_patterns = [
            r"phone|email|linkedin|github|address|mobile|contact",
            r"@|\.com|\.in|\.org|www\.|http",
            r"experience|education|skills|projects|objective|summary",
            r"resume|cv|profile|bio"
        ]
        
        for i, line in enumerate(lines[:10]):
            if not line:
                continue
                
            line_lower = line.lower()
            should_exclude = any(re.search(pattern, line_lower) for pattern in exclusion_patterns)
            
            if should_exclude:
                continue
            
            clean_line = re.sub(r'[^\w\s\'-]', ' ', line)
            words = clean_line.split()
            
            title_words = []
            for word in words:
                if (len(word) >= 2 and word.isalpha() and 
                    (word.istitle() or word.isupper()) and 
                    word.lower() not in ['and', 'the', 'of', 'in', 'at']):
                    title_words.append(word.title())
                else:
                    break
            
            if len(title_words) >= 2:
                return " ".join(title_words[:3])
        
        return "Not found"

    def extract_address_regex(text: str) -> str:
        """Fallback address extraction using regex"""
        text = re.sub(r'\s+', ' ', text)
        
        # Look for city names in the text
        indian_cities = ['pune', 'mumbai', 'delhi', 'bangalore', 'chennai', 'hyderabad', 'kolkata', 'ahmedabad', 'indore']
        for city in indian_cities:
            if city in text.lower():
                return city.title()
        
        keywords = [
            r'address[:\-]?\s*',
            r'location[:\-]?\s*', 
            r'residence[:\-]?\s*',
        ]
        
        for kw in keywords:
            match = re.search(kw + r'([A-Za-z0-9\s,.\-/#]+)', text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                candidate = re.split(r'(?:email|phone|mobile|contact)', candidate, flags=re.IGNORECASE)[0]
                return candidate.strip(" ,.-")
        
        return "Not found"

    try:
        # Extract text from PDF
        raw_text = extract_text_from_pdf(resume_path)
        cleaned_text = clean_text(raw_text)

        print(f"✅ Parsed resume text (first 300 chars):\n{cleaned_text[:300]}")

        # Primary: Use Groq LLM to extract information
        extracted_info = extract_info_with_groq_llm(raw_text)

        # Extract individual fields
        name = extracted_info.get("name", "Not found")
        email = extracted_info.get("email", "Not found") 
        mobile = extracted_info.get("mobile", "Not found")
        address = extracted_info.get("address", "Not found")

        # Fallback: Use regex if LLM extraction failed for any field
        print("🔄 Applying fallback extraction for missing information...")
        
        if name == "Not found":
            print("   Using regex fallback for name...")
            name = extract_name_regex(raw_text)
            
        if email == "Not found":
            print("   Using regex fallback for email...")
            email = extract_email_regex(raw_text)
            
        if mobile == "Not found":
            print("   Using regex fallback for mobile...")
            mobile = extract_mobile_regex(raw_text)
            
        if address == "Not found":
            print("   Using regex fallback for address...")
            address = extract_address_regex(raw_text)

        print(f"✅ Final extracted information:")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Mobile: {mobile}")
        print(f"   Address: {address}")

        return {
            **state, 
            "resume_text": cleaned_text, 
            "mobile": mobile, 
            "email": email, 
            "name": name,
            "address": address
        }

    except Exception as e:
        print(f"❌ Error parsing resume: {e}")
        import traceback
        traceback.print_exc()
        return {
            **state, 
            "resume_text": "", 
            "mobile": "Not found", 
            "email": "Not found", 
            "name": "Not found",
            "address": "Not found"
        }
###############################################################################################################################################################################    

def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """
    Extract skills, education, and experience from resume
    """
    import re, json, ast

    try:
        resume_text = state.get("resume_text", "")

        prompt =PromptTemplate.from_template("""
You are an expert resume parser. Extract the following information from the resume text:

SKILLS: List the top 10 most relevant technical and professional skills mentioned in the resume.

EDUCATION: Extract the HIGHEST degree/qualification from education section. Priority order:
1. PhD/Doctorate
2. Masters/M.Tech/MBA
3. Bachelor's/B.Tech/B.E./B.Sc
4. Diploma
5. Certificate courses
Format as: "Degree Field" (e.g., "B.Tech Computer Science", "Masters Data Science")

EXPERIENCE: Calculate total work experience in years (include internships and full-time jobs).

EXPERIENCE CALCULATION RULES:
1. Count ALL work experience including: Full-time jobs, Internships, Part-time roles
2. EXCLUDE: Academic projects, personal projects, training courses, education duration
3. Parse date ranges carefully:
   - "Feb-Sep 2024" = Feb to Sep = 7 months = 0.6 years
   - "Jan 2022 - Dec 2024" = 3.0 years
   - "Mar 2021 - Present" = calculate from March 2021 to current date
4. Convert months to decimal accurately: 
   - 6 months = 0.5 years, 7 months = 0.6 years, 8 months = 0.7 years
   - 12 months = 1.0 year
5. Sum all qualifying work experiences (jobs + internships)
6. If no work experience found, return "0"

INTERNSHIP HANDLING:
- Internships COUNT as work experience
- Include internship duration in total experience calculation

DATE PARSING EXAMPLES:
- "Feb-Sep 2024" (7 months internship) = 0.6 years experience
- "Software Engineer Jan 2022 - Dec 2023" = 2.0 years
- "Data Scientist Mar 2021 - Present" = calculate current duration
- "Intern Jun-Dec 2023" (6 months) = 0.5 years experience

IMPORTANT NOTES:
- Count both internships and full-time jobs as work experience
- Calculate experience based on actual date ranges
- For education, always pick the highest degree mentioned
- 7 months = 0.6 years (7/12 = 0.58 ≈ 0.6)

Resume:
{resume}

Expected JSON format:
{{"skills": ["skill1", "skill2"], "education": "degree", "experience": "years"}}
""")

        chain = prompt | llm
        response = chain.invoke({"resume": resume_text})
        raw_response = response.content.strip()
        print("✅ LLM raw response:\n", raw_response)

        # Robust JSON extraction - all methods in one function
        analysis_dict = None
        
        # Method 1: Handle LLM prefixes and extract JSON
        try:
            print(f"🔍 Raw response length: {len(raw_response)}")
            
            # Remove markdown code blocks
            cleaned_response = re.sub(r'```(?:json)?\s*', '', raw_response, flags=re.IGNORECASE)
            cleaned_response = re.sub(r'\s*```', '', cleaned_response)
            
            # Remove common prefixes that LLMs add
            prefixes_to_remove = [
                r"Here is the extracted (?:data|information) in (?:the requested )?JSON format:?\s*",
                r"Here's the extracted (?:data|information):?\s*",
                r"The extracted (?:data|information) in JSON format is:?\s*",
                r"JSON response:?\s*",
                r"Response:?\s*"
            ]
            
            for prefix in prefixes_to_remove:
                cleaned_response = re.sub(prefix, '', cleaned_response, flags=re.IGNORECASE)
            
            cleaned_response = cleaned_response.strip()
            print(f"🧹 Cleaned response:\n{cleaned_response[:300]}...")
            
            # Find JSON boundaries - robust approach
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                print(f"✅ Found JSON block:\n{json_str}")
                
                # Try parsing with json.loads
                analysis_dict = json.loads(json_str)
                print("✅ Method 1: Successfully parsed with json.loads")
                
        except json.JSONDecodeError as e:
            print(f"❌ Method 1 JSON decode error: {e}")
        except Exception as e:
            print(f"❌ Method 1 failed: {e}")
        
        # Method 2: Line-by-line approach if Method 1 failed
        if analysis_dict is None:
            try:
                lines = raw_response.split('\n')
                json_started = False
                json_lines = []
                brace_count = 0
                
                for line in lines:
                    line = line.strip()
                    if not json_started and line.startswith('{'):
                        json_started = True
                        json_lines.append(line)
                        brace_count += line.count('{') - line.count('}')
                    elif json_started:
                        json_lines.append(line)
                        brace_count += line.count('{') - line.count('}')
                        if brace_count == 0:
                            break
                
                if json_lines:
                    json_str = '\n'.join(json_lines)
                    print(f"🔧 Method 2 JSON:\n{json_str}")
                    
                    try:
                        analysis_dict = json.loads(json_str)
                        print("✅ Method 2: Successfully parsed with json.loads")
                    except:
                        # Try with ast.literal_eval
                        try:
                            analysis_dict = ast.literal_eval(json_str)
                            print("✅ Method 2: Successfully parsed with ast.literal_eval")
                        except Exception as e2:
                            print(f"❌ Method 2 ast error: {e2}")
                            
            except Exception as e:
                print(f"❌ Method 2 failed: {e}")
        
        # Method 3: Manual regex extraction (last resort)
        if analysis_dict is None:
            try:
                print("🔧 Attempting manual regex extraction...")
                
                # Extract skills array
                skills_pattern = r'"skills":\s*\[(.*?)\]'
                skills_match = re.search(skills_pattern, raw_response, re.DOTALL)
                skills = []
                if skills_match:
                    skills_content = skills_match.group(1)
                    # Extract individual skill items
                    skill_items = re.findall(r'"([^"]+)"', skills_content)
                    skills = skill_items
                    print(f"✅ Extracted skills: {skills}")
                
                # Extract education
                edu_pattern = r'"education":\s*"([^"]*)"'
                edu_match = re.search(edu_pattern, raw_response)
                education = edu_match.group(1) if edu_match else "Unknown"
                print(f"✅ Extracted education: {education}")
                
                # Extract experience
                exp_pattern = r'"experience":\s*"([^"]*)"'
                exp_match = re.search(exp_pattern, raw_response)
                experience = exp_match.group(1) if exp_match else "0"
                print(f"✅ Extracted experience: {experience}")
                
                analysis_dict = {
                    "skills": skills,
                    "education": education,
                    "experience": experience
                }
                print("✅ Manual extraction successful")
                
            except Exception as e:
                print(f"❌ Manual extraction failed: {e}")
        
        # Final fallback to defaults if all methods failed
        if analysis_dict is None:
            print("⚠️ All extraction methods failed, using defaults")
            analysis_dict = {
                "skills": [],
                "education": "Unknown",
                "experience": "0"
            }

        # Ensure all required keys exist and have correct types
        analysis_dict.setdefault("skills", [])
        analysis_dict.setdefault("education", "Unknown")
        analysis_dict.setdefault("experience", "0")
        
        # Validate types
        if not isinstance(analysis_dict["skills"], list):
            analysis_dict["skills"] = []
        if not isinstance(analysis_dict["education"], str):
            analysis_dict["education"] = "Unknown"
        if not isinstance(analysis_dict["experience"], str):
            analysis_dict["experience"] = str(analysis_dict["experience"])

        print("✅ Final parsed analysis:\n", analysis_dict)
        return {**state, "analysis": analysis_dict}

    except Exception as e:
        print(f"❌ Analysis failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}
def compute_similarity(state: ResumeState) -> ResumeState:
    """
    Compute similarity between resume and job description
    """
    jd = state.get("jd_text", "")
    resume = state.get("resume_text", "")
    
    def is_valid_resume(text):
        if len(text.strip().split()) < 50:
            return False
        keywords = ['education', 'experience', 'skills', 'project', 'certification']
        return any(kw in text.lower() for kw in keywords)
    
    def embedding_similarity(jd, resume):
        try:
            embed = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
            jd_vec = embed.embed_query(jd)
            res_vec = embed.embed_query(resume)
            score = cosine_similarity([jd_vec], [res_vec])[0][0]
            print(f"✅ Embedding similarity score: {score}")
            return round(score * 10, 2)  # Normalize to 0–10 scale
        except Exception as e:
            print(f"❌ Embedding similarity failed: {e}")
            return 0
    
    if not is_valid_resume(resume):
        return {
            **state,
            "llm_score": 0,
            "embedding_score": 0,
            "similarity_score": 0
        }

    # 1. LLM-based similarity
    try:
        prompt = PromptTemplate.from_template("""
        Given the job description: {jd}
        And the resume: {resume}
        How well does the resume match the job description?
        Return a score from 0 to 10.
        """)
        chain = prompt | llm
        response = chain.invoke({"jd": jd, "resume": resume})
        match = re.search(r"\b([0-9]{1,2})\b", response.content)
        llm_score = int(match.group(1)) if match else 0
    except Exception as e:
        print(f"❌ LLM similarity failed: {e}")
        llm_score = 0

    # 2. Embedding-based similarity
    embed_score = embedding_similarity(jd, resume)

    # 3. Combined score
    combined_score = round(0.5 * llm_score + 0.5 * embed_score, 2)
    print(f"✅ LLM score: {llm_score}, Embedding score: {embed_score}, Combined score: {combined_score}")
    
    return {
        **state,
        "llm_score": llm_score,
        "embedding_score": embed_score,
        "similarity_score": combined_score
    }

def classify_resume(state: ResumeState) -> ResumeState:
    """
    Classify resume into job category
    """
    try:
        prompt = PromptTemplate.from_template("""
        Classify the resume below into **only one** job category from this list, based on how well it matches the provided job description:

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

        Only return one of the above job categories exactly as-is. No explanation.
        """)
        chain = prompt | llm
        response = chain.invoke({"jd": state.get("jd_text", ""), "resume": state.get("resume_text", "")})
        job_type = response.content.strip()
        print(f"✅ Classified job type: {job_type}")
        return {**state, "job_type": job_type}
    except Exception as e:
        print(f"❌ Classification failed: {e}")
        return {**state, "job_type": "Unknown"}

# def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
#     """
#     Extract skills, education, and experience from resume
#     """
#     try:
#         prompt = PromptTemplate.from_template("""
#         You are an information extraction system.  
#         From the resume text below, extract exactly the following fields and return ONLY valid JSON (no extra words, no explanation):  

#         - **skills** → Top 10 most relevant technical or professional skills (list of strings).  
#         - **education** → Highest education level mentioned (string).  
#         - "experience" → Calculate the total professional work experience in years (with 1 decimal precision). Follow these rules strictly:
#     1. Identify all periods of professional employment from the resume.
#        - Include internships only if they are labeled as work experience or have start and end dates.
#        - Ignore academic projects, coursework, certifications, and volunteer activities unless labeled as work experience.
#     2. For each date range:
#        - Convert start and end months to numeric values.
#        - If only the year is given (e.g., "2020 – 2021"), assume January for start month and December for end month.
#        - If month is missing but year is given for end date, assume December.
#        - If month is missing but year is given for start date, assume January.
#        - If end date is "Present" or "Current", use the current month and year.
#     3. Calculate the month difference, then convert to years with 1 decimal:
#        - Example: 4 months → 0.3 years, 6 months → 0.5 years, 18 months → 1.5 years.
#     4. If periods overlap, count the overlapping months only once.
#     5. Sum all non-overlapping periods to get total experience.
#     6. Output as a decimal string (e.g., "0.4", "2.0", "5.3").
#     7. Never round up to the next year.

#         Resume:
#         {resume}

#         Respond ONLY in this JSON format:
#         {{
#         "skills": ["Python", "TensorFlow", "..."],
#         "education": "Bachelor of Pharmacy",
#         "experience": "0.8"
#         }}
#         """)


#         chain = prompt | llm
#         response = chain.invoke({"resume": state.get("resume_text", "")})
        
#         print("✅ LLM raw response:\n", response.content)

#         try:
#             analysis_dict = json.loads(response.content)
#         except json.JSONDecodeError:
#             try:
#                 import ast
#                 analysis_dict = ast.literal_eval(response.content)
#             except Exception:
#                 analysis_dict = {
#                     "skills": [],
#                     "education": "Unknown",
#                     "experience": "0"
#                 }

#         print("✅ Final parsed analysis:\n", analysis_dict)
#         return {**state, "analysis": analysis_dict}
        
#     except Exception as e:
#         print(f"❌ Analysis failed: {e}")
#         return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}







def score_resume(state: ResumeState) -> ResumeState:
    """
    Calculate final score for the resume
    """
    MIN_SIMILARITY_THRESHOLD = 5  # Adjust as needed
    
    def extract_required_experience(jd_text):
        match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
        return int(match.group(1)) if match else None
    
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})

    # Step 1: Filter out irrelevant resumes
    if similarity < MIN_SIMILARITY_THRESHOLD:
        return {**state, "score": 0, "experience_filtered": False}
    
    print(f"✅ Similarity score: {similarity}")

    # Step 2: Extract experience from resume
    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    # Step 3: Extract required experience from JD
    required_exp = extract_required_experience(state.get("jd_text", ""))
    if required_exp is not None and exp_years < required_exp:
        return {**state, "score": 0, "experience_filtered": True}

    # Step 4: Count skills
    skills = analysis.get("skills", [])
    skills_count = len(skills)

    # Step 5: Normalize scores (all between 0 and 1)
    normalized_similarity = min(similarity / 10.0, 1.0)
    normalized_exp = min(exp_years / 10.0, 1.0)
    normalized_skills = min(skills_count / 10.0, 1.0)

    # Step 6: Weighted score calculation (final score 0–10)
    weighted_score = (0.5 * normalized_similarity) + \
                     (0.2 * normalized_exp) + \
                     (0.3 * normalized_skills)

    final_score = min(weighted_score * 10.0, 10.0)

    print(f"✅ Final score: {round(final_score, 2)}")
    
    return {
        **state,
        "score": round(final_score, 2),
        "experience_filtered": False
    }

# =============================================================================
# 3. UTILITY FUNCTIONS
# =============================================================================

def save_feedback(resume_id, feedback):
    """Save feedback for a resume"""
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")

def rank_top_candidates(processed_resumes):
    """Rank candidates based on their scores"""
    # Only use already scored resumes
    scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]

    # Sort by score
    scored_resumes.sort(key=lambda x: x["score"], reverse=True) 

    # Assign rank
    for i, res in enumerate(scored_resumes, 1):
        res["rank"] = i

    return scored_resumes[:10]  # Top 10 candidates












































# from email.mime.multipart import MIMEMultipart
# from email.mime.text import MIMEText
# import smtplib
# import os
# import streamlit as st

# def send_feedback_email(to_email, feedback_text):
#     from_email = os.getenv("GMAIL_USER")
#     app_password = os.getenv("GMAIL_PASS")

#     subject = "Feedback on Your Resume Submission"

#     if feedback_text.lower() == "accept":
#         html_body = """
#         <p>Dear Candidate,</p>
#         <p>Thank you for applying to Pyrack. We are pleased to inform you that your profile has been shortlisted for further consideration.</p>
#         <p>Our team will reach out to you shortly with the next steps.</p>
#         <p>Best regards,<br>HR Team<br>Pyrack Pvt. Ltd.</p>
#         """
#     else:
#         html_body = """
#         <p>Dear Candidate,</p>
#         <p>Thank you for your interest in Pyrack and for taking the time to apply.</p>
#         <p>After a thorough review, we regret to inform you that we will not be moving forward with your application at this stage.</p>
#         <p>We encourage you to explore future opportunities on our 
#         <a href="https://www.pyrack.com/" target="_blank">Careers Page</a>.</p>
#         <p>Wishing you all the best in your professional journey.</p>
#         <p>Sincerely,<br>HR Team<br>Pyrack Pvt. Ltd.</p>
#         """

#     # ✅ Create email with HTML content
#     msg = MIMEMultipart("alternative")
#     msg["Subject"] = subject
#     msg["From"] = from_email
#     msg["To"] = to_email
#     msg.attach(MIMEText(html_body, "html"))  # ✅ This sends HTML properly

#     print("====== EMAIL CONTENT TO BE SENT ======")
#     print(html_body)
#     print("======================================")

#     try:
#         with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
#             server.login(from_email, app_password)
#             server.sendmail(from_email, to_email, msg.as_string())

#         print(f"✅ Email sent to {to_email}")
#         with open("email_log.txt", "a") as f:
#             f.write(f"Sent to {to_email} with feedback '{feedback_text}'\n")

#     except Exception as e:
#         print("❌ Failed to send email:", str(e))
#         st.error(f"❌ Email send failed: {str(e)}")
