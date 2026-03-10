# HR Hiring Bot 🤖📊

An intelligent, AI-powered HR Assistant built with Streamlit, LangGraph, and Groq. This application automates the recruitment pipeline by analyzing resumes across multiple sources, scoring them against Job Descriptions, and providing an interactive RAG-based Chatbot to query candidate data.

---

## ✨ Features

- **Automated Resume Parsing**: Extracts and analyzes text from PDFs and DOCX files. Integrates OCR (Tesseract) for image-based resumes.
- **Smart Candidate Scoring**: Leverages semantic embeddings and LLM reasoning to evaluate skills, experience, and education against Job Descriptions (JD).
- **Multi-Source Ingestion**: Fetch resumes directly via Gmail, Google Drive, Local Folders, or Manual Uploads.
- **AI Chatbot (RAG)**: Ask contextual questions about your candidate pool, automatically retrieving data via ChromaDB.
- **Analytics Dashboard**: Visualize score distributions, hiring trends, and skill frequencies using Plotly charts.
- **Export to Excel/PDF**: Download comprehensive reports of candidate assessments easily.
- **Template Management**: Save, reuse, and manage multiple JD templates.

## 🛠 Tech Stack

- **UI Framework**: Streamlit
- **LLM Engine**: Groq (Llama Models)
- **Agent Orchestration**: LangChain & LangGraph
- **Vector DB / Embeddings**: ChromaDB & SentenceTransformers
- **Database**: PostgreSQL (via SQLAlchemy)
- **Containerization**: Docker & Docker Compose

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- [Docker & Docker Compose](https://www.docker.com/) (For containerized deployment)
- Tesseract OCR & Poppler (if running locally without Docker)
- API Keys: `GROQ_API_KEY`

### 1. Clone the repository
Ensure you are in the project root directory.

### 2. Set up the Environment
Create a `.env` file in the project directory with the following variables:
```env
GROQ_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://postgres:postgrespassword@db:5432/hr_bot_db
```
*(Optional)* Add Gmail / Google Drive credentials if utilizing those integrations.

### 3. Run with Docker Compose (Recommended)
This will start both the PostgreSQL database and the Streamlit web application.
```bash
docker-compose up --build -d
```
The app will be accessible at: `http://localhost:8501`

### 4. Run Locally (Without Docker)
Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```
Ensure PostgreSQL is running locally and update the `DATABASE_URL` in `.env`. Initialize the DB and run the app:
```bash
streamlit run main.py
```

---

## 📖 Usage Guide
1. **Manage Templates**: Go to the sidebar to add a new Job Description Template.
2. **Process Resumes**: Under the "Process Resumes" tab, select your JD and upload source (Manual, Gmail, etc.) then click "Start Processing".
3. **Analytics**: Switch to the "Analytics" tab to view real-time metrics of your processed candidate pool.
4. **Chatbot**: Go to the "HR Chatbot" tab to ask questions like *"Which candidates have python experience?"* or *"Who scored the highest for the Data Scientist role?"*

## 🤝 Contributing
Contributions, issues, and feature requests are welcome!

## 📜 License
This project is open-source. Please refer to the LICENSE file for details.
