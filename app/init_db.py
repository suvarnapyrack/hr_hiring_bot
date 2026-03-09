import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import engine, Base
# Import ALL models so Base.metadata knows about every table
from app.models import Candidate, JobDescription, Resume, JDTemplate, ChatMessage

print("Creating database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully.")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
