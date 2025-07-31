import json
import os

FEEDBACK_FILE = "saved_feedback.json"

# Save feedback to JSON
def save_feedback(resume_id, feedback):
    feedback_data = []
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            feedback_data = json.load(f)

    feedback_data.append({
        "resume_id": resume_id,
        "feedback": feedback
    })

    with open(FEEDBACK_FILE, "w") as f:
        json.dump(feedback_data, f, indent=4)

# Optional: Read feedback
def load_feedback():
    if os.path.exists(FEEDBACK_FILE):
        with open(FEEDBACK_FILE, "r") as f:
            return json.load(f)
    return []
