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
        SHEET_ID = '10kEyz4UgkQgsxYLHyUUro3uj4Qgk63aQqlDjhiXdqLw'
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.sheet1
        rows = ws.get_all_records()
        df = pd.DataFrame(rows)

        resume_links = df["resume file"].dropna().tolist()
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



def parse_resume(state: Dict) -> Dict:
    """
    Extracts and cleans text from a resume PDF, and retrieves the mobile number, email, and name.
    """
    resume_path = state.get("resume")

    if not resume_path or not os.path.exists(resume_path):
        print("❌ Resume file not found")
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found"}

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
    def extract_email(text: str) -> str:
        """
        Extract an email address from text, handling:
        - Emails with/without spaces
        - Flexible formats
        - Reconstruction from '@' symbol
        - Validation of the final email
        """

        # First, try standard email patterns (no spaces) - must start with letter
        standard_email_pattern = r'\b[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b'
        standard_matches = re.findall(standard_email_pattern, text)
        for email in standard_matches:
            if re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return email

        # Remove common prefixes that interfere with email extraction
        cleaned_text = re.sub(r'\b(India|USA|UK|Canada|Mumbai|Delhi|Bangalore|Pune|Hyderabad|Chennai|Kolkata|Ahmedabad|Indore)\s*[-\s]*', '', text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r'\b\d{5,6}\s*[-\s]*', '', cleaned_text)  # Pin codes
        cleaned_text = re.sub(r'\b\d{10}\s*[-\s]*', '', cleaned_text)   # Phone numbers
        
        # Try standard pattern on cleaned text
        standard_matches = re.findall(standard_email_pattern, cleaned_text)
        for email in standard_matches:
            if re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                return email

        # Find emails with spaces using domain pattern
        domain_pattern = r'@[\s]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        domain_matches = list(re.finditer(domain_pattern, text))
        
        for domain_match in domain_matches:
            domain = re.sub(r'\s+', '', domain_match.group(1))
            at_pos = domain_match.start()

            # Look backwards from @ to find username parts - expand search range
            start_pos = max(0, at_pos - 120)
            before_at = text[start_pos:at_pos]

            # Extract username parts that start with letter and look email-like
            username_patterns = [
                r'([a-zA-Z][a-zA-Z0-9._%+-]*[\s]+[a-zA-Z0-9._%+-]+)[\s]*$',  # Two parts with space (priority)
                r'([a-zA-Z][a-zA-Z0-9._%+-]*[\s]*[a-zA-Z0-9._%+-]*)[\s]*$',  # Must start with letter
                r'([a-zA-Z][a-zA-Z0-9._%+-]*)[\s]*$',  # Single part starting with letter
            ]

            for pattern in username_patterns:
                username_match = re.search(pattern, before_at)
                if username_match:
                    potential_username = username_match.group(1)
                    clean_username = re.sub(r'\s+', '', potential_username)
                    
                    # Filter out invalid usernames
                    if (len(clean_username) >= 2 and 
                        clean_username[0].isalpha() and  # Must start with letter
                        not clean_username.isdigit() and  # Not all numbers
                        not re.match(r'^(India|Indore|\d{5,})', clean_username, re.IGNORECASE)):  # Not location/number
                        
                        email = clean_username + "@" + domain
                        if re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                            return email

        # Try flexible spacing patterns
        flexible_patterns = [
            r'([a-zA-Z][a-zA-Z0-9._%+-]*[\s]+[a-zA-Z0-9._%+-]+)[\s]*@[\s]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',  # Spaced username
            r'([a-zA-Z][a-zA-Z0-9._%+-]*)[\s]+([a-zA-Z0-9._%+-]+)[\s]*@[\s]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'([a-zA-Z][a-zA-Z0-9._%+-]*)[\s]*@[\s]*([a-zA-Z0-9.-]+)[\s]*\.[\s]*([a-zA-Z]{2,})',
        ]
        
        for pattern in flexible_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                if len(groups) == 2:  # Pattern 1: spaced username
                    email = re.sub(r'\s+', '', groups[0]) + "@" + groups[1]
                elif len(groups) == 3 and '.' in groups[2]:
                    email = groups[0] + groups[1] + "@" + groups[2]
                elif len(groups) == 3:
                    email = groups[0] + "@" + groups[1] + "." + groups[2]
                else:
                    continue
                    
                email = re.sub(r'\s+', '', email)
                # Check if username is valid
                username = email.split('@')[0]
                if (len(username) >= 2 and 
                    username[0].isalpha() and 
                    not username.isdigit() and 
                    not re.match(r'^(India|Indore|\d{5,})', username, re.IGNORECASE) and
                    re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email)):
                    return email

        # Last resort: reconstruct around '@' with better filtering
        at_positions = [m.start() for m in re.finditer(r'@', text)]
        for at_pos in at_positions:
            start_search = max(0, at_pos - 40)
            end_search = min(len(text), at_pos + 40)
            before_at = text[start_search:at_pos]
            after_at = text[at_pos+1:end_search]
            
            # Get username parts (must start with letter)
            username_parts = re.findall(r'[a-zA-Z][a-zA-Z0-9._%+-]*', before_at)
            if not username_parts:
                continue
                
            # Take the last valid username part
            username = username_parts[-1]
            
            # Filter out invalid usernames
            if (len(username) >= 2 and 
                username[0].isalpha() and 
                not username.isdigit() and 
                not re.match(r'^(India|Indore|\d{5,})', username, re.IGNORECASE)):
                
                # Get domain parts
                domain_parts = re.findall(r'[a-zA-Z0-9.-]+', after_at)
                if not domain_parts or '.' not in domain_parts[0]:
                    continue
                domain = domain_parts[0]
                
                email = username + "@" + domain
                if re.match(r'^[a-zA-Z][a-zA-Z0-9._%+-]*@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
                    return email

                return "Not found"
    
    def extract_address(text: str) -> str:
        """
        Extract postal address from resume text.
        Handles variations like:
        - "Address: ..."
        - Multi-line addresses
        - Common keywords (Street, Road, Lane, City, State, Zip)
        """

        # Normalize spacing
        text = re.sub(r'\s+', ' ', text)

        # Common address keywords
        keywords = [
            r'address[:\-]?\s*',
            r'location[:\-]?\s*',
            r'residence[:\-]?\s*',
            r'permanent\s+address[:\-]?\s*',
            r'present\s+address[:\-]?\s*',
        ]

        # Pattern: keyword followed by text until a line break or 200 chars max
        for kw in keywords:
            match = re.search(kw + r'([A-Za-z0-9\s,.\-/#]+)', text, re.IGNORECASE)
            if match:
                candidate = match.group(1).strip()
                # Stop at phone/email if they appear after
                candidate = re.split(r'(?:email|e-mail|phone|mobile|contact)', candidate, flags=re.IGNORECASE)[0]
                return candidate.strip(" ,.-")

        # Fallback: try to detect generic address-like patterns
        fallback_pattern = (
            r'([0-9]{1,5}\s+[A-Za-z0-9\s,.\-/#]+(?:street|st\.|road|rd\.|lane|ln\.|avenue|ave\.|city|state|pincode|zip)[A-Za-z0-9\s,.\-/#]*)'
        )
        match = re.search(fallback_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" ,.-")

        return "Not found"


    def extract_mobile(text: str) -> str:
        """Improved mobile extraction with more patterns"""
        # Clean text for better matching
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
            # Match with separators like spaces, dashes, dots
            r"\+91[\s\.-]*([6-9]\d{2})[\s\.-]*(\d{3})[\s\.-]*(\d{4})",
            # Match format: +91 876 735 7785
            r"\+91\s+(\d{3})\s+(\d{3})\s+(\d{4})",
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
        
    def extract_name(text: str) -> str:
        lines = text.strip().split("\n")
        lines = [line.strip() for line in lines if line.strip()]
        
        # Enhanced exclusion patterns
        exclusion_patterns = [
            r"phone|email|linkedin|github|address|mobile|contact|cell",
            r"@|\.com|\.in|\.org|\.net|\.edu|www\.|http|mailto:",
            r"^\+?\d+|phone:\s*\+?\d+",
            r"work experience|experience|education|skills|projects|objective|summary",
            r"resume|cv|curriculum vitae|profile|bio|about",
            r"data scien|engineer|intern|analyst|developer|programmer|manager|consultant",
            r"technologies|pvt|ltd|company|corp|inc|llc|organization",
            r"pune|mumbai|delhi|bangalore|chennai|hyderabad|kolkata|ahmedabad",
            r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february",
            r"202\d|201\d|19\d\d",
            r"street|road|avenue|lane|city|state|zip|pincode|pin",
            r"bachelor|master|phd|btech|mtech|bsc|msc|degree|university|college",
            r"python|java|javascript|html|css|sql|react|node|angular",
            r"certification|certified|course|training|workshop"
        ]
        
        # Collect all name candidates with scoring
        all_candidates = []
        
        # Search through first 15 lines instead of 10
        for i, line in enumerate(lines[:15]):
            if not line:
                continue
                
            # Check if line should be excluded
            line_lower = line.lower()
            should_exclude = False
            for pattern in exclusion_patterns:
                if re.search(pattern, line_lower):
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
            
            # Clean line and extract words
            clean_line = re.sub(r'[^\w\s\'-]', ' ', line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()
            words = clean_line.split()
            
            # Strategy 1: Look for consecutive capitalized words
            caps_sequence = []
            for word in words:
                if len(word) >= 2 and word.isalpha() and word.lower() not in ['and', 'the', 'of', 'in', 'at', 'to', 'for', 'with', 'by']:
                    if word.isupper() or word.istitle():
                        caps_sequence.append(word.title())
                    else:
                        if len(caps_sequence) >= 2:
                            candidate = " ".join(caps_sequence)
                            score = 100 - i * 5
                            if len(caps_sequence) == 2:
                                score += 10
                            elif len(caps_sequence) == 3:
                                score += 5
                            all_candidates.append((candidate, score, i))
                        caps_sequence = []
                else:
                    if len(caps_sequence) >= 2:
                        candidate = " ".join(caps_sequence)
                        score = 100 - i * 5
                        if len(caps_sequence) == 2:
                            score += 10
                        elif len(caps_sequence) == 3:
                            score += 5
                        all_candidates.append((candidate, score, i))
                    caps_sequence = []
            
            # Don't forget the last sequence
            if len(caps_sequence) >= 2:
                candidate = " ".join(caps_sequence)
                score = 100 - i * 5
                if len(caps_sequence) == 2:
                    score += 10
                elif len(caps_sequence) == 3:
                    score += 5
                all_candidates.append((candidate, score, i))
            
            # Strategy 2: Look for title case words at the beginning of line
            title_words = []
            for word in words:
                if len(word) >= 2 and word.isalpha() and (word.istitle() or word.isupper()) and word.lower() not in ['and', 'the', 'of', 'in', 'at', 'to', 'for', 'with', 'by']:
                    title_words.append(word.title())
                else:
                    break
            
            if len(title_words) >= 2:
                candidate = " ".join(title_words[:4])  # Limit to 4 words max
                score = 95 - i * 5  # Slightly lower score than caps sequence
                if len(title_words) == 2:
                    score += 8
                elif len(title_words) == 3:
                    score += 4
                all_candidates.append((candidate, score, i))
        
        # Filter and sort candidates
        valid_candidates = []
        for candidate, score, line_num in all_candidates:
            words = candidate.split()
            if 2 <= len(words) <= 4 and all(len(w) >= 2 for w in words):
                valid_candidates.append((candidate, score, line_num))
        
        # Sort by score (highest first)
        valid_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Return the best candidate
        if valid_candidates:
            return valid_candidates[0][0]
        
        # Fallback 1: Look for any reasonable text in first few lines
        for i, line in enumerate(lines[:5]):
            if not line:
                continue
                
            # Check exclusion
            line_lower = line.lower()
            should_exclude = False
            for pattern in exclusion_patterns:
                if re.search(pattern, line_lower):
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
                
            # Clean and extract first few words
            clean_line = re.sub(r'[^\w\s]', ' ', line)
            clean_line = re.sub(r'\s+', ' ', clean_line).strip()
            words = clean_line.split()
            
            # Take first 2-3 alphabetic words
            name_words = []
            for word in words[:3]:
                if word.isalpha() and len(word) >= 2:
                    name_words.append(word.title())
                else:
                    break
                    
            if len(name_words) >= 2:
                return " ".join(name_words)
        
        # Fallback 2: Look for any line with mixed case letters
        for line in lines[:10]:
            if not line:
                continue
                
            # Check exclusion
            line_lower = line.lower()
            should_exclude = False
            for pattern in exclusion_patterns:
                if re.search(pattern, line_lower):
                    should_exclude = True
                    break
            
            if should_exclude:
                continue
                
            # Look for lines with both uppercase and lowercase letters
            if any(c.isupper() for c in line) and any(c.islower() for c in line):
                words = re.findall(r'[A-Za-z]{2,}', line)
                if len(words) >= 2:
                    return " ".join(words[:3]).title()
        
        return "Not found"

    try:
        raw_text = extract_text_from_pdf(resume_path)
        cleaned_text = clean_text(raw_text)

        # Use raw text for pattern matching to preserve formatting
        mobile = extract_mobile(raw_text)
        email = extract_email(raw_text)  # Also use raw text for better email detection
        name = extract_name(raw_text)
        address=extract_address(raw_text)

        print(f"✅ Parsed resume text (first 300 chars):\n{cleaned_text[:300]}")
        print(f"✅ Raw text sample for debugging:\n{raw_text[:500]}")  # Debug raw text
        print(f"✅ Extracted mobile: {mobile}")
        print(f"✅ Extracted email: {email}")
        print(f"✅ Extracted name: {name}")
        print(f"✅ Extracted Address :{address}")

        return {**state, "resume_text": cleaned_text, "mobile": mobile, "email": email, "name": name,"address": address}

    except Exception as e:
        print(f"❌ Error parsing resume: {e}")
        import traceback
        traceback.print_exc()
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found"}
###############################################################################################################################################################################    
# def parse_resume(state: dict) -> dict:
#     import re
    
#     # 1️⃣ Extract text
#     raw_text = extract_text_from_pdf(state["resume_path"])
#     print("\n=== RAW TEXT (first 300 chars) ===")
#     print(raw_text[:300], "\n")

#     # 2️⃣ Clean text
#     cleaned_text = clean_text(raw_text)
#     print("\n=== CLEANED TEXT (first 300 chars) ===")
#     print(cleaned_text[:300], "\n")

#     # 3️⃣ Extract entities
#     mobile = extract_mobile(cleaned_text)
#     email = extract_email(cleaned_text)
#     name = extract_name(cleaned_text)

#     print(f"[DEBUG] Mobile Extracted: {mobile}")
#     print(f"[DEBUG] Email Extracted: {email}")
#     print(f"[DEBUG] Name Extracted: {name}")

#     # 4️⃣ Store results in state
#     state["mobile"] = mobile
#     state["email"] = email
#     state["name"] = name

#     return state

# def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
#     """
#     Extract skills, education, and experience from resume
#     """
#     try:
        
#         prompt = PromptTemplate.from_template("""
# From the resume text below, extract the following and return ONLY valid JSON (no explanation or formatting):
# - Top 10 relevant skills (as a list of strings)
# - Education level (as a single string)
# -A string representing the total years of professional work experience.Only count if explicit work experience is mentioned in a particular section (e.g., "2 years", "3.5 years", "Worked from 2019 to 2021").If the candidate is a fresher or no experience is mentioned, return "0".
# Resume:
# {resume}

# Respond ONLY in this JSON format:
# {{
#   "skills": ["..."],
#   "education": "...",
#   "experience": "..."
# }}""")

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
# def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
#     """
#     Extract skills, education, and experience from resume
#     """
#     import re, json, ast

#     try:
#         resume_text = state.get("resume_text", "")

#         prompt = PromptTemplate.from_template("""
# You are an information extraction system.  
# Your task is to read the resume text and extract exactly this data:  
# - Top 10 relevant skills (list of strings)  
# - Education level (string)  
# - total_experience_years: Total professional work experience in years (string, e.g., "2", "3.5", "0")

# Rules for total_experience_years:
# 1. Count ONLY if the resume explicitly states the duration in years/months or has start and end dates (e.g., "Aug 2024 - Dec 2024").
# 2. If duration is in months, convert to years with one decimal place (e.g., "5 months" → "0.4").
# 3. If multiple experiences are listed, sum them up.
# 4. Do NOT infer or guess based on skills, job titles, or education.
# 5. If no explicit duration is mentioned, return "0".
# 6. Never round up — keep the exact lower bound.

# You must respond with **only valid JSON**. No explanation. No extra words.  
# If a field is missing in the resume, use defaults: [] for skills, "Unknown" for education, "0" for experience.  

# Resume:
# {resume}

# JSON response format (strictly follow this):
# {
#   "skills": ["Python", "TensorFlow", "..."],
#   "education": "Bachelor of Pharmacy",
#   "experience": "0.8"
# }
# """)

#         chain = prompt | llm
#         response = chain.invoke({"resume": resume_text})
#         raw_response = response.content.strip()
#         print("✅ LLM raw response:\n", raw_response)

#         # Clean up potential markdown wrappers
#         raw_response = re.sub(r"```(json)?", "", raw_response).strip()

#         # Extract JSON portion
#         if "{" in raw_response and "}" in raw_response:
#             json_str = raw_response[raw_response.find("{"): raw_response.rfind("}") + 1]
#         else:
#             json_str = raw_response

#         # Parse JSON safely
#         try:
#             analysis_dict = json.loads(json_str)
#         except json.JSONDecodeError:
#             try:
#                 analysis_dict = ast.literal_eval(json_str)
#             except Exception:
#                 analysis_dict = {
#                     "skills": [],
#                     "education": "Unknown",
#                     "experience": "0"
#                 }

#         # Ensure keys exist
#         analysis_dict.setdefault("skills", [])
#         analysis_dict.setdefault("education", "Unknown")
#         analysis_dict.setdefault("experience", "0")

#         print("✅ Final parsed analysis:\n", analysis_dict)
#         return {**state, "analysis": analysis_dict}

#     except Exception as e:
#         print(f"❌ Analysis failed: {e}")
#         return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}
def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """
    Extract skills, education, and experience from resume
    """
    import re, json, ast

    try:
        resume_text = state.get("resume_text", "")

        prompt = PromptTemplate.from_template("""
You are an information extraction system.  
Your task is to read the resume text and extract exactly this data:  
- Top 10 relevant skills (list of strings)  
- Education level (string)  
- total_experience_years: Total professional work experience in years (string, e.g., "2", "3.5", "0")

Rules for total_experience_years:
1. Count ONLY if the resume explicitly states the duration in years/months or has start and end dates (e.g., "Aug 2024 - Dec 2024").
2. If duration is in months, convert to years with one decimal place (e.g., "5 months" → "0.4").
3. If multiple experiences are listed, sum them up.
4. Do NOT infer or guess based on skills, job titles, or education.
5. If no explicit duration is mentioned, return "0".
6. Never round up — keep the exact lower bound.

IMPORTANT: Respond with ONLY valid JSON. No explanations, no additional text, no markdown.

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
