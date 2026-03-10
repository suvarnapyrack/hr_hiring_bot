import os
import imaplib
import email
from datetime import datetime, timedelta
from .shared_types import ResumeState

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

    if limit and len(downloaded) > limit:
        downloaded = downloaded[:limit]

    if downloaded:
        print(f"✅ Successfully fetched {len(downloaded)} resumes from Gmail.")
        return {**state, "resumes": downloaded}
    else:
        print(f"❌ No resumes found in Gmail in the last {days_limit} days.")
        return {**state, "resumes": []}
