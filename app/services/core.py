import os
import re
import pdfplumber
from pdf2image import convert_from_path
import pytesseract

def clean_text(text: str) -> str:
    """Clean extracted text by removing extra whitespaces and non-ASCII characters."""
    if not text:
        return ""
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = re.sub(r"[ \t]+", " ", line)
        line = re.sub(r"[^\x00-\x7F]+", " ", line)
        line = line.strip()
        if line:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

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
            
        if len(text.strip()) < 50:
            print(f"⚠️ Standard extraction yielded only {len(text.strip())} chars. Flagging for OCR.")
            requires_ocr = True
            
    except Exception as e:
        print(f"⚠️ Error during standard extraction: {e}. Flagging for OCR.")
        requires_ocr = True

    return text, requires_ocr

def extract_text_with_ocr(filepath: str) -> str:
    """
    Fallback method to extract text from a PDF file using OCR.
    """
    try:
        print(f"🔍 Attempting OCR extraction on: {os.path.basename(filepath)}")
        images = convert_from_path(filepath)
        text_content = []
        
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
            
    except Exception as e:
        print(f"❌ Error during OCR extraction: {e}")
        return ""
