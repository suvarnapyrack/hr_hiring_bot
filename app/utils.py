import functools
import builtins
builtins.print = functools.partial(print, flush=True)

import os
import re
import io   
import mimetypes
from pathlib import Path
from datetime import datetime, timedelta
import json
import pdfplumber
import imaplib
import email
import pandas as pd
import requests
from sklearn.metrics.pairwise import cosine_similarity
from typing import Dict, List, Optional, TypedDict

from dotenv import load_dotenv
load_dotenv(override=True)

import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from langchain_openai import OpenAIEmbeddings

from langchain_community.embeddings import HuggingFaceEmbeddings

from langchain_core.prompts import PromptTemplate
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END

# Initialize LLM — using Groq cloud API
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0
)



##############################################################################################################################################################################
def extract_candidate_data_from_main_sheet(main_sheet_id=None, limit=2):
    """
    Extract candidate data from main sheet including stipend and experience
    Added limit parameter to process only first N candidates
    UPDATED: Now includes tracking sheet creation and duplicate checking
    """
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    # Define constants first
    CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH") 
    MAIN_SHEET_ID = os.getenv("MAIN_SHEET_ID")

    try:
        print(f"🔄 Extracting candidate data from main sheet (limit: {limit})...")

        # Authenticate
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        gc = gspread.authorize(creds)

        # Use provided sheet ID or default
        if not main_sheet_id:
            main_sheet_id = MAIN_SHEET_ID
        
        print(f"📊 Using main sheet ID: {main_sheet_id}")
        
        # Read main sheet
        sh = gc.open_by_key(main_sheet_id)
        ws = sh.sheet1
        
        # ✅ NEW: Create or get tracking sheet
        try:
            tracking_sheet = sh.worksheet("processing_tracker")
            print("✅ Found existing tracking sheet")
        except:
            print("🆕 Creating new tracking sheet...")
            tracking_sheet = sh.add_worksheet(title="processing_tracker", rows=3000, cols=8)
            headers = ['Row_Number', 'Name', 'Email', 'Mobile', 'Processing_Status','address','stipend','experience','Processing_Date', 'Final_Score', 'Resume_URL']
            tracking_sheet.insert_row(headers, 1)
            print("✅ Created new tracking sheet")
        
        # ✅ NEW: Get already processed candidates
        processed_emails = set()
        processed_mobiles = set()
        last_row_processed = 0
        
        try:
            tracking_data = tracking_sheet.get_all_records()
            for record in tracking_data:
                if record.get('Processing_Status') == 'COMPLETED':
                    # ✅ FIXED: Handle case-sensitive field names and multiple possible keys
                    email = str(record.get('Email', record.get('email', ''))).strip().lower()
                    mobile = str(record.get('Mobile', record.get('mobile', ''))).strip()
                    
                    # ✅ ADDED: Extract address, stipend, experience from tracking sheet
                    address = str(record.get('address', record.get('Address', ''))).strip()
                    stipend = str(record.get('stipend', record.get('Stipend', ''))).strip()
                    experience = str(record.get('experience', record.get('Experience', ''))).strip()
                    
                    if email and email != 'not found':
                        processed_emails.add(email)
                    if mobile and mobile != 'not found':
                        processed_mobiles.add(mobile)
                    
                    # ✅ FIXED: Handle Row_Number field name variations
                    row_num = record.get('Row_Number', record.get('row_number', 0))
                    if isinstance(row_num, (int, float)) and row_num > last_row_processed:
                        last_row_processed = int(row_num)
            
            print(f"📊 Found {len(processed_emails)} processed emails, {len(processed_mobiles)} processed mobiles")
            print(f"📍 Last row processed: {last_row_processed}")
        except Exception as tracking_error:
            print(f"📊 Error reading tracking data: {tracking_error}")
            print("📊 No previous processing data found")
        
        # Get all data from main sheet — use get_all_values() to avoid
        # gspread.exceptions.GSpreadException on duplicate/empty column headers
        try:
            all_values = ws.get_all_values()
        except Exception as sheet_read_err:
            print(f"❌ Error reading main sheet: {sheet_read_err}")
            return [], gc, main_sheet_id, tracking_sheet

        if not all_values or len(all_values) < 2:
            print("❌ Main sheet is empty or has only a header row")
            return [], gc, main_sheet_id, tracking_sheet

        headers = all_values[0]
        rows = all_values[1:]

        # Deduplicate column headers (append _2, _3 etc to duplicates)
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

        # Remove completely empty rows
        df = df.replace('', pd.NA).dropna(how='all').replace(pd.NA, '')

        # ✅ NEW: Add row numbers for tracking and filter from last processed + 1
        df = df.reset_index(drop=True)
        df['original_row_number'] = df.index + 2  # +2 because Excel starts at 1 and has header
        
        # Start from next unprocessed row
        start_from_row = last_row_processed + 1
        if start_from_row > 2:  # 2 because first data row is 2
            df = df[df['original_row_number'] >= start_from_row]
            print(f"📊 Starting from row {start_from_row} (continuing from last run)")
        
        # Apply limit (only first N candidates)
        if limit and limit > 0:
            df = df.head(limit)
            print(f"📊 Limited to first {limit} rows")
        
        print(f"✅ Main sheet columns: {df.columns.tolist()}")
        print(f"📊 Total rows after removing empty and applying limit: {len(df)}")
        
        if len(df) == 0:
            print("❌ No new data found in main sheet (all candidates may be already processed)")
            return [], gc, main_sheet_id, tracking_sheet
        
        # Column mapping - find best matching columns
        name_col = None
        mobile_col = None
        email_col = None
        address_col = None
        resume_col = None
        stipend_col = None
        experience_col = None
        
        # Find columns with flexible matching
        for col in df.columns:
            if col == 'original_row_number':
                continue
                
            col_lower = col.lower().strip()
            print(f"🔍 Checking column: '{col}' -> '{col_lower}'")
            
            if 'name' in col_lower and not name_col:
                name_col = col
                print(f"✅ Name column: {col}")
            elif any(x in col_lower for x in ['mobile', 'phone', 'number']) and not mobile_col:
                mobile_col = col
                print(f"✅ Mobile column: {col}")
            elif 'email' in col_lower and not email_col:
                email_col = col
                print(f"✅ Email column: {col}")
            elif any(x in col_lower for x in ['address', 'location']) and not address_col:
                address_col = col
                print(f"✅ Address column: {col}")
            elif any(x in col_lower for x in ['resume', 'url', 'link', 'cv']) and not resume_col:
                resume_col = col
                print(f"✅ Resume column: {col}")
            elif any(x in col_lower for x in ['stipend', 'salary', 'expected', 'amount', 'pay']) and not stipend_col:
                stipend_col = col
                print(f"✅ Stipend column: {col}")
            elif any(x in col_lower for x in ['experience', 'exp', 'years']) and 'work' not in col_lower and not experience_col:
                experience_col = col
                print(f"✅ Experience column: {col}")
        
        print(f"\n📋 Final Column Mapping:")
        print(f"   Name: {name_col}")
        print(f"   Mobile: {mobile_col}")
        print(f"   Email: {email_col}")
        print(f"   Address: {address_col}")
        print(f"   Resume: {resume_col}")
        print(f"   Stipend: {stipend_col}")
        print(f"   Experience: {experience_col}")
        
        # Extract candidate data with all fields
        candidate_data = []
        for idx, row in df.iterrows():
            original_row = row.get('original_row_number', idx + 2)
            
            # Extract all data with safe fallbacks
            name_val = str(row.get(name_col, '')).strip() if name_col else ''
            mobile_val = str(row.get(mobile_col, '')).strip() if mobile_col else ''
            email_val = str(row.get(email_col, '')).strip() if email_col else ''
            address_val = str(row.get(address_col, '')).strip() if address_col else ''
            resume_val = str(row.get(resume_col, '')).strip() if resume_col else ''
            stipend_val = str(row.get(stipend_col, '')).strip() if stipend_col else ''
            experience_val = str(row.get(experience_col, '')).strip() if experience_col else ''
            
            # Skip completely empty rows
            if not any([name_val, mobile_val, email_val, resume_val]):
                print(f"⚠️ Skipping empty row {original_row}")
                continue
            
            # Clean up 'nan' and empty values
            def clean_value(val, default='Not found'):
                if val in ['nan', 'None', 'null', '', 'NaN']:
                    return default
                return val
            
            name_val = clean_value(name_val)
            mobile_val = clean_value(mobile_val)
            email_val = clean_value(email_val)
            address_val = clean_value(address_val)
            resume_val = clean_value(resume_val, '')
            stipend_val = clean_value(stipend_val, 'Not specified')
            experience_val = clean_value(experience_val, 'Not specified')
            
            # ✅ NEW: Check if candidate already processed
            email_check = email_val.lower().strip() if email_val != 'Not found' else None
            mobile_check = mobile_val.strip() if mobile_val != 'Not found' else None
            
            if (email_check and email_check in processed_emails) or (mobile_check and mobile_check in processed_mobiles):
                print(f"⏭️ Skipping already processed candidate: {name_val} (Row: {original_row})")
                continue
            
            # Create candidate info with ALL required fields
            candidate_info = {
                # ✅ NEW: Add tracking info
                'original_row_number': original_row,
                
                # From Main Sheet
                'name': name_val,
                'mobile': mobile_val,
                'email': email_val,
                'address': address_val,
                'resume_url': resume_val,
                'stipend': stipend_val,          # ✅ FROM MAIN SHEET
                'experience': experience_val,    # ✅ FROM MAIN SHEET
                
                # From LangGraph (will be updated during processing)
                'skills': [],
                'education': '',
                'final_score': 0,
                'similarity_score': 0,
                'rank': ''
            }
            
            candidate_data.append(candidate_info)
            print(f"✅ Added candidate {len(candidate_data)}: {name_val} (Row: {original_row}) | Email: {email_val} | Stipend: {stipend_val} | Experience: {experience_val}")
        
        print(f"\n✅ Extracted {len(candidate_data)} NEW candidates from main sheet (limited to {limit})")
        
        # Debug: Show first few candidates
        if candidate_data:
            print("\n📋 First 3 NEW candidates extracted:")
            for i, candidate in enumerate(candidate_data[:3], 1):
                print(f"{i}. Name: {candidate['name']} (Row: {candidate['original_row_number']})")
                print(f"   Email: {candidate['email']}")
                print(f"   Mobile: {candidate['mobile']}")
                print(f"   Address: {candidate['address']}")  # ✅ ADDED
                print(f"   Stipend: {candidate['stipend']}")
                print(f"   Experience: {candidate['experience']}")
                print(f"   Resume URL: {candidate['resume_url'][:500]}..." if len(candidate['resume_url']) > 500 else f"   Resume URL: {candidate['resume_url']}")
                print()
        
        return candidate_data, gc, main_sheet_id, tracking_sheet
        
    except Exception as e:
        print(f"❌ Error extracting data from main sheet: {e}")
        import traceback
        traceback.print_exc()
        return [], None, None, None

def fetch_from_drive(state=None, limit=5):
    """
    Fetch and process candidates from Google Drive with complete data extraction
    Added limit parameter to process only first N candidates
    UPDATED: Now includes duplicate prevention and tracking
    """
    def get_file_id(drive_url):
        if not drive_url or drive_url.strip() == '':
            return None
        if "id=" in drive_url:
            return drive_url.split("id=")[1]
        elif "/d/" in drive_url:
            return drive_url.split("/d/")[1].split("/")[0]
        return None

    try:
        print(f"🚀 Starting Google Drive processing (limit: {limit})...")
        
        # Step 1: Extract candidate data from main sheet with limit and tracking
        candidate_data, gc, sheet_id, tracking_sheet = extract_candidate_data_from_main_sheet(limit=limit)
        
        if not candidate_data:
            print("❌ No new candidate data found")
            return []
        
        print(f"📊 Processing {len(candidate_data)} NEW candidates (limited to {limit})...")
        
        # Step 2: Create or get analysis sheet for real-time updates
        try:
            sh = gc.open_by_key(sheet_id)
            try:
                analysis_sheet = sh.worksheet("candidate analysis")
                print("✅ Found existing candidate analysis sheet")
            except:
                print("🆕 Creating new candidate analysis sheet...")
                analysis_sheet = create_candidate_analysis_sheet(gc, sheet_id, candidate_data)
        except:
            analysis_sheet = None
        
        if not analysis_sheet:
            print("❌ Failed to create/get analysis sheet")
            return candidate_data
            
        CREDENTIALS_PATH = os.getenv("CREDENTIALS_PATH")
        
        # Step 3: Set up Drive API for resume download
        SCOPES = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_PATH, scopes=SCOPES
        )
        drive_service = build("drive", "v3", credentials=creds)
        os.makedirs("resumes/from_drive", exist_ok=True)
        
        processed_candidates = []
        
        # Step 4: Process each candidate
        for i, candidate in enumerate(candidate_data):
            row_number = candidate.get('original_row_number')
            print(f"\n🔄 Processing candidate {i+1}/{len(candidate_data)}: {candidate.get('name', 'Unknown')} (Row: {row_number})")
            print(f"📧 Email: {candidate.get('email', 'Not found')}")
            print(f"📱 Mobile: {candidate.get('mobile', 'Not found')}")
            print(f"💰 Stipend: {candidate.get('stipend', 'Not specified')}")
            print(f"📅 Experience: {candidate.get('experience', 'Not specified')}")
            
            try:
                resume_url = candidate.get('resume_url', '')
                if not resume_url or resume_url.strip() == '' or resume_url == 'Not found':
                    print("⚠️ No resume URL found for this candidate")
                    candidate['final_score'] = 0
                    processed_candidates.append(candidate)
                    
                    # ✅ FIXED: Update tracking sheet with correct field order
                    from datetime import datetime
                    tracking_row = [
                        row_number, candidate.get('name', ''), candidate.get('email', ''), 
                        candidate.get('mobile', ''), 'COMPLETED',
                        candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, ''
                    ]
                    tracking_sheet.append_row(tracking_row)
                    
                    # ✅ NEW: Real-time update to analysis sheet
                    if analysis_sheet:
                        try:
                            candidate_row = [
                                candidate.get('name', ''),
                                candidate.get('email', ''),
                                candidate.get('mobile', ''),
                                candidate.get('address', ''),
                                '',  # skills (empty for no resume)
                                '',  # education (empty for no resume)
                                candidate.get('stipend', ''),
                                candidate.get('experience', ''),
                                0,   # final_score
                                0,   # similarity_score
                                'N/A', # rank
                                '',  # resume_url (empty)
                                f"Row {row_number} - No Resume"
                            ]
                            analysis_sheet.append_row(candidate_row)
                            print(f"✅ Added to analysis sheet: {candidate.get('name')} - No Resume")
                        except Exception as sheet_error:
                            print(f"⚠️ Error updating analysis sheet: {sheet_error}")
                    continue
                
                print(f"🔗 Resume URL: {resume_url}")
                
                # Download and process resume
                file_id = get_file_id(resume_url)
                if not file_id:
                    print(f"❌ Could not extract file_id from: {resume_url}")
                    candidate['final_score'] = 0
                    processed_candidates.append(candidate)
                    
                    # ✅ FIXED: Update tracking sheet with correct field order
                    from datetime import datetime
                    tracking_row = [
                        row_number, candidate.get('name', ''), candidate.get('email', ''), 
                        candidate.get('mobile', ''), 'ERROR',
                        candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, resume_url
                    ]
                    tracking_sheet.append_row(tracking_row)
                    
                    # ✅ NEW: Real-time update to analysis sheet
                    if analysis_sheet:
                        try:
                            candidate_row = [
                                candidate.get('name', ''),
                                candidate.get('email', ''),
                                candidate.get('mobile', ''),
                                candidate.get('address', ''),
                                '',  # skills
                                '',  # education
                                candidate.get('stipend', ''),
                                candidate.get('experience', ''),
                                0,   # final_score
                                0,   # similarity_score
                                'N/A', # rank
                                resume_url,
                                f"Row {row_number} - Invalid URL"
                            ]
                            analysis_sheet.append_row(candidate_row)
                            print(f"✅ Added to analysis sheet: {candidate.get('name')} - ERROR")
                        except Exception as sheet_error:
                            print(f"⚠️ Error updating analysis sheet: {sheet_error}")
                    continue
                
                try:
                    # Download the resume
                    print(f"⬇️ Downloading resume with file_id: {file_id}")
                    request = drive_service.files().get_media(fileId=file_id)
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                    
                    fh.seek(0)
                    file_path = Path("resumes/from_drive") / f"{file_id}.pdf"
                    with open(file_path, "wb") as f:
                        f.write(fh.read())
                    
                    # Add filepath and filename so process_resumes can find the file
                    candidate['filepath'] = str(file_path)
                    candidate['filename'] = f"{candidate.get('name', file_id)}.pdf"
                    
                    print(f"✅ Downloaded: {file_path}")
                    
                    # Process the resume using LangGraph pipeline
                    temp_state = {
                        "resume": str(file_path),
                        "jd_text": state.get("jd_text", "") if state else ""
                    }
                    
                    # Parse resume (extract basic info if missing from main sheet)
                    temp_state = parse_resume(temp_state)
                    
                    # Update candidate info with extracted data ONLY if missing from main sheet
                    if candidate.get('name') == 'Not found' and temp_state.get('name'):
                        candidate['name'] = temp_state.get('name', 'Not found')
                    if candidate.get('mobile') == 'Not found' and temp_state.get('mobile'):
                        candidate['mobile'] = temp_state.get('mobile', 'Not found')
                    if candidate.get('email') == 'Not found' and temp_state.get('email'):
                        candidate['email'] = temp_state.get('email', 'Not found')
                    
                    # LangGraph Analysis - extract skills, education, experience from resume
                    temp_state = analyze_skills_education_experience(temp_state)
                    
                    # Update candidate with LangGraph results
                    candidate['skills'] = temp_state.get('analysis', {}).get('skills', [])
                    candidate['education'] = temp_state.get('analysis', {}).get('education', '')
                    
                    # Note: Keep experience from main sheet, don't override with resume extraction
                    # candidate['experience'] stays as extracted from main sheet
                    
                    # Compute similarity with job description if provided
                    if temp_state.get("jd_text"):
                        temp_state = compute_similarity(temp_state)
                        temp_state = score_resume(temp_state)
                        
                        candidate['similarity_score'] = temp_state.get('similarity_score', 0)
                        candidate['final_score'] = temp_state.get('score', 0)
                    else:
                        print("⚠️ No job description provided, skipping similarity and scoring")
                        candidate['similarity_score'] = 0
                        candidate['final_score'] = 0
                    
                    print(f"✅ Final score for {candidate.get('name', 'Unknown')}: {candidate['final_score']}")
                    print(f"🎯 Skills found: {len(candidate.get('skills', []))}")
                    
                    # ✅ FIXED: Update tracking sheet with correct field order including address, stipend, experience
                    from datetime import datetime
                    tracking_row = [
                        row_number, candidate.get('name', ''), candidate.get('email', ''), 
                        candidate.get('mobile', ''), 'COMPLETED',
                        candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                        candidate.get('final_score', 0), resume_url
                    ]
                    tracking_sheet.append_row(tracking_row)
                    
                    # ✅ NEW: Real-time update to analysis sheet for each candidate
                    if analysis_sheet:
                        try:
                            candidate_row = [
                                candidate.get('name', ''),
                                candidate.get('email', ''),
                                candidate.get('mobile', ''),
                                candidate.get('address', ''),
                                ', '.join(candidate.get('skills', [])),
                                candidate.get('education', ''),
                                candidate.get('stipend', ''),
                                candidate.get('experience', ''),
                                candidate.get('final_score', 0),
                                candidate.get('similarity_score', 0),
                                '', # rank will be updated later
                                candidate.get('resume_url', ''),
                                f"Row {row_number}"
                            ]
                            analysis_sheet.append_row(candidate_row)
                            print(f"✅ Added to analysis sheet: {candidate.get('name')} - Score: {candidate.get('final_score')}")
                        except Exception as sheet_error:
                            print(f"⚠️ Error updating analysis sheet: {sheet_error}")
                    
                    
                except Exception as download_error:
                    print(f"❌ Error downloading/processing resume: {download_error}")
                    candidate['final_score'] = 0
                    candidate['similarity_score'] = 0
                    candidate['skills'] = []
                    candidate['education'] = ''
                    
                    # ✅ FIXED: Update tracking sheet with correct field order
                    from datetime import datetime
                    tracking_row = [
                        row_number, candidate.get('name', ''), candidate.get('email', ''), 
                        candidate.get('mobile', ''), 'ERROR',
                        candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, resume_url
                    ]
                    tracking_sheet.append_row(tracking_row)
                    
                    # ✅ NEW: Real-time update to analysis sheet
                    if analysis_sheet:
                        try:
                            candidate_row = [
                                candidate.get('name', ''),
                                candidate.get('email', ''),
                                candidate.get('mobile', ''),
                                candidate.get('address', ''),
                                '',  # skills
                                '',  # education
                                candidate.get('stipend', ''),
                                candidate.get('experience', ''),
                                0,   # final_score
                                0,   # similarity_score
                                'N/A', # rank
                                resume_url,
                                f"Row {row_number} - Download Error"
                            ]
                            analysis_sheet.append_row(candidate_row)
                            print(f"✅ Added to analysis sheet: {candidate.get('name')} - ERROR")
                        except Exception as sheet_error:
                            print(f"⚠️ Error updating analysis sheet: {sheet_error}")
                
            except Exception as e:
                print(f"❌ Error processing candidate {candidate.get('name', 'Unknown')}: {e}")
                candidate['final_score'] = 0
                candidate['similarity_score'] = 0
                candidate['skills'] = []
                candidate['education'] = ''
                
                # ✅ FIXED: Update tracking sheet with correct field order
                from datetime import datetime
                tracking_row = [
                    row_number, candidate.get('name', ''), candidate.get('email', ''), 
                    candidate.get('mobile', ''), 'ERROR',
                    candidate.get('address', ''), candidate.get('stipend', ''), candidate.get('experience', ''),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 0, 
                    candidate.get('resume_url', '')
                ]
                tracking_sheet.append_row(tracking_row)
                
                # ✅ NEW: Real-time update to analysis sheet
                if analysis_sheet:
                    try:
                        candidate_row = [
                            candidate.get('name', ''),
                            candidate.get('email', ''),
                            candidate.get('mobile', ''),
                            candidate.get('address', ''),
                            '',  # skills
                            '',  # education
                            candidate.get('stipend', ''),
                            candidate.get('experience', ''),
                            0,   # final_score
                            0,   # similarity_score
                            'N/A', # rank
                            candidate.get('resume_url', ''),
                            f"Row {row_number} - Processing Error"
                        ]
                        analysis_sheet.append_row(candidate_row)
                        print(f"✅ Added to analysis sheet: {candidate.get('name')} - ERROR")
                    except Exception as sheet_error:
                        print(f"⚠️ Error updating analysis sheet: {sheet_error}")
            
            processed_candidates.append(candidate)
        
        # Step 5: Rank candidates based on final score
        scored_candidates = [c for c in processed_candidates if c.get('final_score', 0) > 0]
        scored_candidates.sort(key=lambda x: x['final_score'], reverse=True)
        
        # Assign ranks
        for i, candidate in enumerate(scored_candidates, 1):
            candidate['rank'] = i
        
        # Candidates without scores get no rank
        unscored_candidates = [c for c in processed_candidates if c.get('final_score', 0) == 0]
        for candidate in unscored_candidates:
            candidate['rank'] = 'N/A'
        
        # Step 6: Update rankings in analysis sheet (final step)
        if analysis_sheet and scored_candidates:
            print(f"\n🔄 Updating rankings in analysis sheet...")
            try:
                # Get all data from analysis sheet to update ranks
                analysis_data = analysis_sheet.get_all_records()
                
                # Update ranks for scored candidates
                for candidate in scored_candidates:
                    candidate_name = candidate.get('name', '')
                    candidate_email = candidate.get('email', '')
                    
                    # Find matching row in analysis sheet and update rank
                    for row_idx, row_data in enumerate(analysis_data, start=2):  # start=2 because row 1 is header
                        if (row_data.get('Name') == candidate_name and 
                            row_data.get('Email') == candidate_email):
                            analysis_sheet.update(f'K{row_idx}', candidate.get('rank', ''))  # Column K is rank
                            break
                
                print(f"✅ Updated rankings for {len(scored_candidates)} candidates")
                
            except Exception as rank_error:
                print(f"⚠️ Error updating rankings: {rank_error}")
        
        # Remove the old batch update since we're doing real-time updates
        # update_success = update_candidate_analysis_sheet(analysis_sheet, processed_candidates)
        
        update_success = True  # Since we're doing real-time updates
        
        if update_success:
            print(f"\n🎉 Processing complete!")
            print(f"📊 {len(scored_candidates)} candidates scored and ranked (from {limit} processed)")
            print(f"📋 Results saved to 'candidate analysis' sheet")
            print(f"📝 Progress tracked in 'processing_tracker' sheet")
            
            # Display top 5 candidates
            if scored_candidates:
                print("\n🏆 TOP 5 CANDIDATES:")
                print("-" * 130)
                print(f"{'Rank':<4} {'Name':<25} {'Score':<8} {'Stipend':<15} {'Experience':<12} {'Row':<5} {'Email':<30}")
                print("-" * 130)
                for candidate in scored_candidates[:5]:
                    print(f"{candidate.get('rank', 'N/A'):<4} "
                          f"{candidate.get('name', 'Unknown')[:24]:<25} "
                          f"{candidate.get('final_score', 0):<8.2f} "
                          f"{str(candidate.get('stipend', 'Not specified'))[:14]:<15} "
                          f"{str(candidate.get('experience', 'Not specified'))[:11]:<12} "
                          f"{candidate.get('original_row_number', 'N/A'):<5} "
                          f"{candidate.get('email', 'Not found')[:29]:<30}")
        
        return processed_candidates

    except Exception as e:
        print("❌ Error in fetch_from_drive:", e)
        import traceback
        traceback.print_exc()
        return []

def run_complete_resume_analysis(jd_text="", source_type="drive", limit=5):
    """
    Main function to run complete resume analysis workflow
    Added limit parameter to process only first N resumes
    UPDATED: Now automatically continues from last processed position
    """
    print(f"🚀 Starting complete resume analysis (limit: {limit})...")
    print(f"🔄 Will automatically continue from last processed position...")
    
    # Set up state with job description
    state = {
        "jd_text": jd_text,
        "source_type": source_type
    }
    
    print(f"📝 Job Description provided: {'Yes' if jd_text else 'No'}")
    print(f"📊 Source type: {source_type}")
    print(f"🔢 Processing limit: {limit} resumes")
    
    # Process based on source type
    if source_type == "drive":
        processed_candidates = fetch_from_drive(state, limit=limit)
    elif source_type == "folder":
        processed_candidates = fetch_from_folder(state, limit=limit)  # You'll need to add limit to this function too
    elif source_type == "gmail":
        processed_candidates = fetch_from_gmail(state, limit=limit)   # You'll need to add limit to this function too
    else:
        print("❌ Unknown source type")
        return []
    
    print(f"\n✅ Analysis complete! Processed {len(processed_candidates)} NEW candidates (limited to {limit}).")
    print(f"🔄 Next run will automatically continue from next unprocessed candidates.")
    return processed_candidates


def test_complete_analysis_limited():
    """
    Test function to run the complete analysis with limit
    UPDATED: Now demonstrates continuation functionality
    """
    sample_jd = """
    We are looking for a Data Analyst with experience in SQL, Python, and data visualization.
    Required skills: SQL, Python, Tableau, Excel, Data Analysis, Statistics
    Experience: 2-4 years preferred
    Location: Remote/Hybrid
    """
    
    print("🧪 Testing complete analysis workflow with continuation...")
    
    # First run - process first 10 resumes
    print("\n" + "="*60)
    print("FIRST RUN - Processing first 10 resumes")
    print("="*60)
    
    results1 = run_complete_resume_analysis(
        jd_text=sample_jd,
        source_type="drive",
        limit=2
    )
    
    # Second run - will automatically continue from where first run left off
    print("\n" + "="*60)
    print("SECOND RUN - Automatically continuing from last position")
    print("="*60)
    
    results2 = run_complete_resume_analysis(
        jd_text=sample_jd,
        source_type="drive",
        limit=2
    )
    
    # Third run - will continue from where second run left off
    print("\n" + "="*60)
    print("THIRD RUN - Continuing again...")
    print("="*60)
    
    results3 = run_complete_resume_analysis(
        jd_text=sample_jd,
        source_type="drive",
        limit=2
    )
    
    print("\n🎯 FINAL SUMMARY:")
    print(f"📊 First run processed: {len(results1)} candidates")
    print(f"📊 Second run processed: {len(results2)} candidates")
    print(f"📊 Third run processed: {len(results3)} candidates")
    print(f"📊 Total NEW candidates processed: {len(results1) + len(results2) + len(results3)}")
    print(f"✅ No duplicates processed - each candidate processed only once!")
    print(f"📝 Check 'processing_tracker' sheet to see processing history")
    
    if len(results1) > 0:
        print(f"🔄 All runs completed successfully with automatic continuation")
    elif len(results1) == 0 and len(results2) == 0 and len(results3) == 0:
        print(f"ℹ️ No new candidates found - all may be already processed")
    
    return results1, results2, results3
from .shared_types import ResumeState

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.langgraph_flow import ResumeState

def choose_source(state: ResumeState) -> ResumeState:
    source_type = state.get("source_type", "folder")
    print(f"✅ Chosen source: {source_type}")
    return {**state, "source_type": source_type}

def fetch_resumes_from_gmail(user_email: str, app_password: str, download_dir: str = "resumes/gmail", days_limit: int = 2) -> list[dict]:
    os.makedirs(download_dir, exist_ok=True)
    allowed_ext = (".pdf", ".doc", ".docx")
    downloaded = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(user_email, app_password)
        mail.select("inbox")

        date_since = (datetime.now() - timedelta(days=days_limit)).strftime("%d-%b-%Y")
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

        return downloaded

    except Exception as e:
        print(f"❌ Error fetching resumes from Gmail: {e}")
        return []

def fetch_from_gmail(state: dict, download_dir: str = "resumes/gmail", limit: int = 10, days_limit: int = 2) -> dict:
    user_email = os.getenv("GMAIL_USER")
    app_password = os.getenv("GMAIL_PASS")

    if not user_email or not app_password:
        print("❌ Gmail credentials not found in environment variables.")
        return {**state, "resumes": []}

    downloaded = fetch_resumes_from_gmail(user_email, app_password, download_dir, days_limit)

    # Optional: limit the total number returned based on the 'limit' parameter
    if limit and len(downloaded) > limit:
        downloaded = downloaded[:limit]

    if downloaded:
        print(f"✅ Successfully fetched {len(downloaded)} resumes from Gmail.")
        return {**state, "resumes": downloaded}
    else:
        print(f"❌ No resumes found in Gmail in the last {days_limit} days.")
        return {**state, "resumes": []}

def create_candidate_analysis_sheet(gc, sheet_id, candidate_data):
    try:
        sh = gc.open_by_key(sheet_id)
        
        try:
            existing_sheet = sh.worksheet('candidate analysis')
            print("⚠️ 'candidate analysis' sheet already exists. Clearing it...")
            existing_sheet.clear()
            analysis_sheet = existing_sheet
        except gspread.exceptions.WorksheetNotFound:
            print("🔄 Creating new 'candidate analysis' sheet...")
            analysis_sheet = sh.add_worksheet(
                title='candidate analysis',
                rows=1000,
                cols=12
            )
        
        headers = [
            'Serial No',
            'Name',
            'Mobile',
            'Email', 
            'Address',
            'Stipend',
            'Final Score',
            'Similarity Score',
            'Experience',
            'Top Skills',
            'Rank',
            'Analysis Date',
            'Status'
        ]
        
        analysis_sheet.update('A1:M1', [headers])
        
        analysis_sheet.format('A1:M1', {
            'textFormat': {'bold': True},
            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
        })
        
        print("✅ Successfully created 'candidate analysis' sheet with headers")
        return analysis_sheet
        
    except Exception as e:
        print(f"❌ Error creating analysis sheet: {e}")
        return None

def update_candidate_analysis_sheet(analysis_sheet, candidate_data):
    """
    Update the candidate analysis sheet with processed data including final scores
    """
    try:
        # Prepare data for bulk update
        rows_to_update = []
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for i, candidate in enumerate(candidate_data, 1):
            # Format skills as comma-separated string
            skills_str = ', '.join(candidate.get('skills', [])[:5]) if candidate.get('skills') else 'Not analyzed'
            
            row = [
                i,  # Serial No
                candidate.get('name', 'Not found'),
                candidate.get('mobile', 'Not found'), 
                candidate.get('email', 'Not found'),
                candidate.get('address', 'Not found'),
                candidate.get('stipend', 'Not specified'),
                candidate.get('final_score', 0),
                candidate.get('similarity_score', 0),
                candidate.get('experience', '0'),
                skills_str,
                candidate.get('rank', ''),
                current_date,
                'Processed' if candidate.get('final_score', 0) > 0 else 'Pending'
            ]
            rows_to_update.append(row)
        
        # Update all rows at once (more efficient)
        if rows_to_update:
            range_name = f'A2:M{len(rows_to_update) + 1}'
            analysis_sheet.update(range_name, rows_to_update)
            
            print(f"✅ Updated candidate analysis sheet with {len(rows_to_update)} records")
            
            # Apply conditional formatting for final scores
            try:
                # Format final score column (G) with colors
                analysis_sheet.format('G:G', {
                    'numberFormat': {
                        'type': 'NUMBER',
                        'pattern': '0.00'
                    }
                })
                
                print("✅ Applied formatting to analysis sheet")
                
            except Exception as format_error:
                print(f"⚠️ Formatting failed (data still saved): {format_error}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating analysis sheet: {e}")
        return False

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
    print("✅ Manual upload selected")
    return state

def extract_text_with_ocr(filepath: str) -> str:
    """
    Fallback method to extract text from a PDF file using OCR (Optical Character Recognition).
    Used when standard text extraction fails (e.g., image-based PDFs).
    Requires 'pdf2image' and 'pytesseract' libraries, and poppler/tesseract installed on the system.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
        
        print(f"🔍 Attempting OCR extraction on: {os.path.basename(filepath)}")
        # Convert PDF pages to images
        images = convert_from_path(filepath)
        text_content = []
        
        # Run OCR on each image
        for i, image in enumerate(images):
            print(f"   Processing page {i+1}/{len(images)}...")
            page_text = pytesseract.image_to_string(image)
            text_content.append(page_text)
            
        full_text = "\n".join(text_content)
        
        if len(full_text.strip()) > 50:
            print(f"✅ OCR extraction successful ({len(full_text)} characters)")
            return full_text
        else:
            print("⚠️ OCR extraction yielded little to no text.")
            return ""
            
    except ImportError:
        print("❌ OCR libraries missing. Please install 'pdf2image' and 'pytesseract'.")
        return ""
    except Exception as e:
        print(f"❌ Error during OCR extraction: {e}")
        return ""

def extract_text_from_pdf(filepath: str) -> tuple[str, bool]:
    """
    Extracts text from a PDF file using pdfplumber.
    Returns a tuple: (extracted_text, requires_ocr_flag)
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")

    text = ""
    requires_ocr = False
    
    try:
        with pdfplumber.open(filepath) as pdf:
            text = "\n".join(
                [page.extract_text() or "" for page in pdf.pages]
            )
            
        # If extraction is very short, it might be an image-based PDF
        if len(text.strip()) < 50:
            print(f"⚠️ Standard extraction yielded only {len(text.strip())} chars. Flagging for OCR.")
            requires_ocr = True
            
    except Exception as e:
        print(f"⚠️ Error during standard extraction: {e}. Flagging for OCR.")
        requires_ocr = True

    return text, requires_ocr

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

def parse_resume(state: Dict) -> Dict:
    """
    Extracts and cleans text from a resume PDF, and uses Groq Llama3 to extract candidate information.
    Falls back to regex-based extraction if LLM fails.
    """
    resume_path = state.get("resume")

    if not resume_path or not os.path.exists(resume_path):
        print("❌ Resume file not found")
        return {**state, "resume_text": "", "mobile": "Not found", "email": "Not found", "name": "Not found", "address": "Not found", "requires_ocr": False}

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
            
            # Initialize Groq LLM
            llm = ChatGroq(
                model="llama-3.3-70b-versatile", 
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
        if resume_path.lower().endswith('.pdf'):
            raw_text, requires_ocr = extract_text_from_pdf(resume_path)
            
            # If standard extraction flagged OCR, attempt it here
            if requires_ocr:
                print(f"🔄 Standard extraction yielded little text. Attempting OCR on {resume_path}...")
                ocr_text = extract_text_with_ocr(resume_path)
                if ocr_text:
                    raw_text = ocr_text
                    
        elif resume_path.lower().endswith(('.docx', '.doc')):
            with open(resume_path, 'r', encoding='utf-8') as f:
                 raw_text = f.read()
            requires_ocr = False
        else:
            raw_text = ""
            requires_ocr = False
            
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

def analyze_skills_education_experience(state: ResumeState) -> ResumeState:
    """
    Extract skills, education, and experience from resume
    """
    import re, json, ast

    try:
        resume_text = state.get("resume_text", "")
        
        if not resume_text.strip():
            print("❌ No resume text found")
            return {**state, "analysis": {"skills": [], "education": "Unknown", "experience": "0"}}

        from datetime import datetime as dt_now
        today_date = dt_now.now().strftime("%B %d, %Y")  # e.g. "March 10, 2026"

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

        print("✅ Extracted JSON string:\n", json_str)

        analysis_dict = None
        try:
            analysis_dict = json.loads(json_str)
            print("✅ JSON parsing successful")
        except json.JSONDecodeError as e:
            print(f"❌ JSON decode error: {e}")
            try:
                analysis_dict = ast.literal_eval(json_str)
                print("✅ AST parsing successful")
            except Exception as e2:
                print(f"❌ AST parsing also failed: {e2}")
                analysis_dict = {
                    "skills": [],
                    "education": "Unknown",
                    "experience": "0"
                }

        if analysis_dict:
            analysis_dict.setdefault("skills", [])
            analysis_dict.setdefault("education", "Unknown")
            analysis_dict.setdefault("experience", "0")
            
            if not isinstance(analysis_dict["skills"], list):
                analysis_dict["skills"] = []
                
            print("✅ Final parsed analysis:\n", analysis_dict)
        else:
            analysis_dict = {
                "skills": [],
                "education": "Unknown", 
                "experience": "0"
            }

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
    jd = state.get("jd_text", "").strip()
    resume = state.get("resume_text", "").strip()
    
    print(f"✅ JD length: {len(jd)} characters")
    print(f"✅ Resume length: {len(resume)} characters")
    
    if not jd or not resume:
        print("❌ Missing JD or resume text")
        return {
            **state,
            "llm_score": 0,
            "embedding_score": 0,
            "similarity_score": 0
        }
    
    def is_valid_resume(text):
        if len(text.strip().split()) < 50:
            print("❌ Resume too short")
            return False
        keywords = ['education', 'experience', 'skills', 'project', 'certification']
        has_keywords = any(kw in text.lower() for kw in keywords)
        print(f"✅ Resume has keywords: {has_keywords}")
        return has_keywords
    
    def embedding_similarity(jd_text, resume_text):
        try:
            print("🔄 Computing embedding similarity...")
            from langchain_community.embeddings import HuggingFaceEmbeddings
            
            embed = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2",
                model_kwargs={'device': 'cpu'}
            )
            
            print("🔄 Creating embeddings...")
            jd_vec = embed.embed_query(jd_text)
            res_vec = embed.embed_query(resume_text)
            
            print(f"✅ JD embedding shape: {len(jd_vec)}")
            print(f"✅ Resume embedding shape: {len(res_vec)}")
            
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            
            score = cosine_similarity([jd_vec], [res_vec])[0][0]
            normalized_score = round(float(score) * 10, 2)
            
            print(f"✅ Raw cosine similarity: {score}")
            print(f"✅ Normalized embedding score (0-10): {normalized_score}")
            
            return normalized_score
            
        except Exception as e:
            print(f"❌ Embedding similarity failed: {e}")
            import traceback
            traceback.print_exc()
            return 0
    
    if not is_valid_resume(resume):
        print("❌ Resume validation failed")
        return {
            **state,
            "llm_score": 0,
            "embedding_score": 0,
            "similarity_score": 0
        }

    llm_score = 0
    try:
        print("🔄 Computing LLM similarity...")
        prompt = PromptTemplate.from_template("""
        Analyze how well this resume matches the job description and provide a score from 0 to 10.
        
        Job Description: {jd}
        
        Resume: {resume}
        
        Respond with ONLY a single number from 0 to 10 (no explanation).
        """)
        chain = prompt | llm
        response = chain.invoke({"jd": jd, "resume": resume})
        
        import re
        numbers = re.findall(r'\b([0-9](?:\.[0-9])?|10(?:\.0)?)\b', response.content)
        if numbers:
            llm_score = float(numbers[0])
            print(f"✅ LLM score extracted: {llm_score}")
        else:
            print(f"❌ No valid score found in LLM response: {response.content}")
            llm_score = 0
            
    except Exception as e:
        print(f"❌ LLM similarity failed: {e}")
        llm_score = 0

    embed_score = embedding_similarity(jd, resume)

    combined_score = round(0.6 * llm_score + 0.4 * embed_score, 2)
    
    print(f"✅ Final scores - LLM: {llm_score}, Embedding: {embed_score}, Combined: {combined_score}")
    
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
        chain = prompt | llm
        response = chain.invoke({
            "jd": state.get("jd_text", ""), 
            "resume": state.get("resume_text", "")
        })

        job_type = getattr(response, "content", response).strip()
        print(f"✅ Classified job type: {job_type}")

        return {**state, "job_type": job_type}

    except Exception as e:
        import traceback
        print(f"❌ Classification failed: {e}")
        traceback.print_exc()
        return {**state, "job_type": "Unknown"}

def score_resume(state: ResumeState) -> ResumeState:
    """
    Calculate final score for the resume
    """
    MIN_SIMILARITY_THRESHOLD = 5
    
    def extract_required_experience(jd_text):
        match = re.search(r"(\d+)[+\s]*years? of experience", jd_text.lower())
        return int(match.group(1)) if match else None
    
    similarity = state.get("similarity_score", 0)
    analysis = state.get("analysis", {})

    if similarity < MIN_SIMILARITY_THRESHOLD:
        return {**state, "score": 0, "experience_filtered": False}
    
    print(f"✅ Similarity score: {similarity}")

    req_exp = extract_required_experience(state.get("jd_text", ""))
    candidate_exp = float(analysis.get("experience", 0))

    if req_exp is not None and candidate_exp < req_exp:
        print(f"❌ Rejected: Needs {req_exp}+ years, has {candidate_exp} years")
        return {**state, "score": 0, "experience_filtered": True}

    score = similarity
    print(f"✅ Final adjusted score: {score}")

    return {**state, "score": score, "experience_filtered": False}

def save_to_db_node(state: ResumeState) -> ResumeState:
    """
    LangGraph node to save the final processed state into PostgreSQL.
    """
    from app.database import get_db
    from app.crud import create_or_update_candidate, save_resume_analysis, create_job_description
    
    # Needs to run within a DB session
    db_gen = get_db()
    db = next(db_gen)
    
    print("💾 [DB Node] Saving candidate and resume to PostgreSQL...")
    try:
        # 1. Save Candidate
        candidate_data = {
            "name": state.get("name", "Unknown"),
            "email": state.get("email", "Unknown"),
            "mobile": state.get("mobile", "Unknown"),
            "address": state.get("address", "Unknown"),
            "skills": state.get("analysis", {}).get("skills", []),
            "education": state.get("analysis", {}).get("education", "Unknown"),
            "experience": state.get("analysis", {}).get("experience", "0")
        }
        candidate = create_or_update_candidate(db, candidate_data)
        
        # 2. Save Job Description (Optional, but good for linking)
        # We assume jd_text is the same. Job Type comes from classification or defaults.
        job_type = state.get("job_type", "General")
        job = create_job_description(db, job_type, state.get("jd_text", ""))
        
        # 3. Save Resume Analysis Link
        resume_record = save_resume_analysis(
            db=db,
            candidate_id=candidate.id,
            file_path=state.get("resume", "Unknown_Path"),
            source=state.get("source_type", "unknown"),
            result_state=state,
            job_id=job.id
        )
        
        print(f"✅ [DB Node] Saved candidate {candidate.name} (ID: {candidate.id}) and resume (ID: {resume_record.id})")
        # Store DB ID in state for potential later use
        state["db_id"] = resume_record.id
        
    except Exception as e:
        print(f"❌ [DB Node] Error saving to DB: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        
    return state

    exp_str = analysis.get("experience", "0")
    match = re.search(r"[\d.]+", exp_str)
    exp_years = float(match.group()) if match else 0.0

    required_exp = extract_required_experience(state.get("jd_text", ""))
    if required_exp is not None and exp_years < required_exp:
        return {**state, "score": 0, "experience_filtered": True}

    skills = analysis.get("skills", [])
    skills_count = len(skills)

    normalized_similarity = min(similarity / 10.0, 1.0)
    normalized_exp = min(exp_years / 10.0, 1.0)
    normalized_skills = min(skills_count / 10.0, 1.0)

    weighted_score = (0.4 * normalized_similarity) + \
                     (0.2 * normalized_exp) + \
                     (0.3 * normalized_skills)

    final_score = min(weighted_score * 10.0, 10.0)

    print(f"✅ Final score: {round(final_score, 2)}")
    
    return {
        **state,
        "score": round(final_score, 2),
        "experience_filtered": False
    }

def save_feedback(resume_id, feedback):
    """Save feedback for a resume"""
    with open("feedback.json", "a") as f:
        f.write(json.dumps({"resume_id": resume_id, "feedback": feedback}) + "\n")

def rank_top_candidates(processed_resumes):
    """Rank candidates based on their scores"""
    scored_resumes = [res for res in processed_resumes if res.get("score", 0) > 0]
    scored_resumes.sort(key=lambda x: x["score"], reverse=True) 

    for i, res in enumerate(scored_resumes, 1):
        res["rank"] = i

    return scored_resumes[:10]

# =============================================================================
# TESTING FUNCTIONS
# =============================================================================





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
