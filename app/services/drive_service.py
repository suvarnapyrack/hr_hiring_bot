import os
import io
import gspread
import pandas as pd
from pathlib import Path
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from .shared_types import ResumeState

# Forward declarations for functions that will be in other modules but are called here
# In a real refactor, we would handle circular dependencies better.
# For now, we will import them locally within functions if needed.

def extract_candidate_data_from_main_sheet(main_sheet_id=None, limit=2):
    """
    Extract candidate data from main sheet including stipend and experience
    """
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH") 
    MAIN_SHEET_ID = os.getenv("MAIN_SHEET_ID")

    try:
        print(f"🔄 Extracting candidate data from main sheet (limit: {limit})...")

        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        gc = gspread.authorize(creds)

        if not main_sheet_id:
            main_sheet_id = MAIN_SHEET_ID
        
        print(f"📊 Using main sheet ID: {main_sheet_id}")
        
        sh = gc.open_by_key(main_sheet_id)
        ws = sh.sheet1
        
        try:
            tracking_sheet = sh.worksheet("processing_tracker")
            print("✅ Found existing tracking sheet")
        except:
            print("🆕 Creating new tracking sheet...")
            tracking_sheet = sh.add_worksheet(title="processing_tracker", rows=3000, cols=8)
            headers = ['Row_Number', 'Name', 'Email', 'Mobile', 'Processing_Status','address','stipend','experience','Processing_Date', 'Final_Score', 'Resume_URL']
            tracking_sheet.insert_row(headers, 1)
            print("✅ Created new tracking sheet")
        
        processed_emails = set()
        processed_mobiles = set()
        last_row_processed = 0
        
        try:
            tracking_data = tracking_sheet.get_all_records()
            for record in tracking_data:
                if record.get('Processing_Status') == 'COMPLETED':
                    email = str(record.get('Email', record.get('email', ''))).strip().lower()
                    mobile = str(record.get('Mobile', record.get('mobile', ''))).strip()
                    
                    if email and email != 'not found':
                        processed_emails.add(email)
                    if mobile and mobile != 'not found':
                        processed_mobiles.add(mobile)
                    
                    row_num = record.get('Row_Number', record.get('row_number', 0))
                    if isinstance(row_num, (int, float)) and row_num > last_row_processed:
                        last_row_processed = int(row_num)
            
            print(f"📊 Found {len(processed_emails)} processed emails, {len(processed_mobiles)} processed mobiles")
        except Exception as tracking_error:
            print(f"📊 Error reading tracking data: {tracking_error}")
        
        try:
            all_values = ws.get_all_values()
        except Exception as sheet_read_err:
            print(f"❌ Error reading main sheet: {sheet_read_err}")
            return [], gc, main_sheet_id, tracking_sheet

        if not all_values or len(all_values) < 2:
            return [], gc, main_sheet_id, tracking_sheet

        headers = all_values[0]
        rows = all_values[1:]

        seen_headers = {}
        clean_headers = []
        for h in headers:
            h = h.strip()
            if h == "":
                h = f"_empty_{len(clean_headers)}"
            if h in seen_headers:
                seen_headers[h] += 1
                h = f"{h}_{seen_headers[h]}"
            else:
                seen_headers[h] = 1
            clean_headers.append(h)

        all_data = [dict(zip(clean_headers, row)) for row in rows]
        df = pd.DataFrame(all_data)
        df = df.replace('', pd.NA).dropna(how='all').replace(pd.NA, '')
        df = df.reset_index(drop=True)
        df['original_row_number'] = df.index + 2 
        
        start_from_row = last_row_processed + 1
        if start_from_row > 2:
            df = df[df['original_row_number'] >= start_from_row]
        
        if limit and limit > 0:
            df = df.head(limit)
        
        if len(df) == 0:
            return [], gc, main_sheet_id, tracking_sheet
        
        name_col = mobile_col = email_col = address_col = resume_col = stipend_col = experience_col = None
        
        for col in df.columns:
            if col == 'original_row_number': continue
            col_lower = col.lower().strip()
            if 'name' in col_lower and not name_col: name_col = col
            elif any(x in col_lower for x in ['mobile', 'phone', 'number']) and not mobile_col: mobile_col = col
            elif 'email' in col_lower and not email_col: email_col = col
            elif any(x in col_lower for x in ['address', 'location']) and not address_col: address_col = col
            elif any(x in col_lower for x in ['resume', 'url', 'link', 'cv']) and not resume_col: resume_col = col
            elif any(x in col_lower for x in ['stipend', 'salary', 'expected', 'amount', 'pay']) and not stipend_col: stipend_col = col
            elif any(x in col_lower for x in ['experience', 'exp', 'years']) and 'work' not in col_lower and not experience_col: experience_col = col
        
        candidate_data = []
        for idx, row in df.iterrows():
            original_row = row.get('original_row_number', idx + 2)
            name_val = str(row.get(name_col, '')).strip() if name_col else ''
            mobile_val = str(row.get(mobile_col, '')).strip() if mobile_col else ''
            email_val = str(row.get(email_col, '')).strip() if email_col else ''
            address_val = str(row.get(address_col, '')).strip() if address_col else ''
            resume_val = str(row.get(resume_col, '')).strip() if resume_col else ''
            stipend_val = str(row.get(stipend_col, '')).strip() if stipend_col else ''
            experience_val = str(row.get(experience_col, '')).strip() if experience_col else ''
            
            if not any([name_val, mobile_val, email_val, resume_val]): continue
            
            def clean_value(val, default='Not found'):
                if val in ['nan', 'None', 'null', '', 'NaN']: return default
                return val
            
            name_val = clean_value(name_val)
            mobile_val = clean_value(mobile_val)
            email_val = clean_value(email_val)
            address_val = clean_value(address_val)
            resume_val = clean_value(resume_val, '')
            stipend_val = clean_value(stipend_val, 'Not specified')
            experience_val = clean_value(experience_val, 'Not specified')
            
            email_check = email_val.lower().strip() if email_val != 'Not found' else None
            mobile_check = mobile_val.strip() if mobile_val != 'Not found' else None
            
            if (email_check and email_check in processed_emails) or (mobile_check and mobile_check in processed_mobiles):
                continue
            
            candidate_info = {
                'original_row_number': original_row,
                'name': name_val,
                'mobile': mobile_val,
                'email': email_val,
                'address': address_val,
                'resume_url': resume_val,
                'stipend': stipend_val,
                'experience': experience_val,
                'skills': [],
                'education': '',
                'final_score': 0,
                'similarity_score': 0,
                'rank': ''
            }
            candidate_data.append(candidate_info)
        
        return candidate_data, gc, main_sheet_id, tracking_sheet
        
    except Exception as e:
        print(f"❌ Error extracting data from main sheet: {e}")
        return [], None, None, None

def create_candidate_analysis_sheet(gc, sheet_id, candidate_data):
    """
    Create a new worksheet for candidate analysis.
    """
    print("🔄 Creating 'candidate analysis' worksheet...")
    try:
        sh = gc.open_by_key(sheet_id)
        ws = sh.add_worksheet(title="candidate analysis", rows="1000", cols="20")
        headers = ["Name", "Email", "Mobile", "Address", "Skills", "Education", "Stipend", "Experience", "Final Score", "Similarity Score", "Rank", "Resume URL", "Notes"]
        ws.insert_row(headers, 1)
        return ws
    except Exception as e:
        print(f"❌ Error creating analysis sheet: {e}")
        return None

def fetch_from_drive(state=None, limit=5):
    """
    Fetch and process candidates from Google Drive.
    """
    from .parser_service import parse_resume, analyze_skills_education_experience, compute_similarity, score_resume

    def get_file_id(drive_url):
        if not drive_url or drive_url.strip() == '': return None
        if "id=" in drive_url: return drive_url.split("id=")[1]
        elif "/d/" in drive_url: return drive_url.split("/d/")[1].split("/")[0]
        return None

    try:
        print("🔄 Initiating Google Drive resume fetch process...")
        candidate_data, gc, sheet_id, tracking_sheet = extract_candidate_data_from_main_sheet(limit=limit)
        if not candidate_data: 
            print("❌ No candidate data extracted from main sheet.")
            return []
        
        try:
            sh = gc.open_by_key(sheet_id)
            try:
                analysis_sheet = sh.worksheet("candidate analysis")
            except:
                analysis_sheet = create_candidate_analysis_sheet(gc, sheet_id, candidate_data)
        except:
            analysis_sheet = None
        
        CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPES)
        drive_service = build("drive", "v3", credentials=creds)
        os.makedirs("resumes/from_drive", exist_ok=True)
        
        processed_candidates = []
        for i, candidate in enumerate(candidate_data):
            row_number = candidate.get('original_row_number')
            try:
                resume_url = candidate.get('resume_url', '')
                if not resume_url or resume_url.strip() == '' or resume_url == 'Not found':
                    candidate['final_score'] = 0
                    processed_candidates.append(candidate)
                    tracking_row = [row_number, candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), 'COMPLETED', candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, '']
                    tracking_sheet.append_row(tracking_row)
                    if analysis_sheet:
                        analysis_sheet.append_row([candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), candidate.get('address', ''), '', '', candidate.get('stipend', ''), candidate.get('experience', ''), 0, 0, 'N/A', '', f"Row {row_number} - No Resume"])
                    continue
                
                file_id = get_file_id(resume_url)
                if not file_id:
                    candidate['final_score'] = 0
                    processed_candidates.append(candidate)
                    tracking_row = [row_number, candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), 'ERROR', candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, resume_url]
                    tracking_sheet.append_row(tracking_row)
                    if analysis_sheet:
                        analysis_sheet.append_row([candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), candidate.get('address', ''), '', '', candidate.get('stipend', ''), candidate.get('experience', ''), 0, 0, 'N/A', resume_url, f"Row {row_number} - Invalid URL"])
                    continue
                
                print(f"📥 Downloading resume file ID: {file_id}...")
                request = drive_service.files().get_media(fileId=file_id)
                fh = io.BytesIO()
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done: _, done = downloader.next_chunk()
                
                fh.seek(0)
                file_path = Path("resumes/from_drive") / f"{file_id}.pdf"
                with open(file_path, "wb") as f: f.write(fh.read())
                print(f"✅ Downloaded resume to {file_path}")
                
                candidate['filepath'] = str(file_path)
                temp_state = {"resume": str(file_path), "jd_text": state.get("jd_text", "") if state else ""}
                temp_state = parse_resume(temp_state)
                
                if candidate.get('name') == 'Not found' and temp_state.get('name'): candidate['name'] = temp_state.get('name', 'Not found')
                if candidate.get('mobile') == 'Not found' and temp_state.get('mobile'): candidate['mobile'] = temp_state.get('mobile', 'Not found')
                if candidate.get('email') == 'Not found' and temp_state.get('email'): candidate['email'] = temp_state.get('email', 'Not found')
                
                temp_state = analyze_skills_education_experience(temp_state)
                candidate['skills'] = temp_state.get('analysis', {}).get('skills', [])
                candidate['education'] = temp_state.get('analysis', {}).get('education', '')
                
                if temp_state.get("jd_text"):
                    temp_state = compute_similarity(temp_state)
                    temp_state = score_resume(temp_state)
                    candidate['similarity_score'] = temp_state.get('similarity_score', 0)
                    candidate['final_score'] = temp_state.get('score', 0)
                
                tracking_row = [row_number, candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), 'COMPLETED', candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), candidate.get('final_score', 0), resume_url]
                tracking_sheet.append_row(tracking_row)
                
                if analysis_sheet:
                    analysis_sheet.append_row([candidate.get('name', ''), candidate.get('email', ''), candidate.get('mobile', ''), candidate.get('address', ''), ', '.join(candidate.get('skills', [])), candidate.get('education', ''), candidate.get('stipend', ''), candidate.get('experience', ''), candidate.get('final_score', 0), candidate.get('similarity_score', 0), '', candidate.get('resume_url', ''), f"Row {row_number}"])
                
            except Exception as e:
                print(f"❌ Error processing candidate: {e}")
            
            processed_candidates.append(candidate)
        
        return processed_candidates

    except Exception as e:
        print("❌ Error in fetch_from_drive:", e)
        return []
