# """
# chatbot.py — AI HR Chatbot using RAG (Retrieval-Augmented Generation)
# Uses ChromaDB for vector storage + Groq LLM for answering HR questions
# based on the candidate data already in the database.
# """

# import os
# from typing import List, Dict, Optional
# from sqlalchemy.orm import Session
# from app.models import Candidate, Resume


# # ─── Build candidate documents ────────────────────────────────────────────────

# def _get_candidate_documents(db: Session) -> tuple[List[str], List[dict], List[str]]:
#     """
#     Pull all candidates + their best resume scores from the DB.
#     Returns (documents, metadatas, ids) ready for ChromaDB ingestion.
#     """
#     results = (
#         db.query(Candidate, Resume)
#         .join(Resume, Resume.candidate_id == Candidate.id)
#         .order_by(Resume.final_score.desc())
#         .all()
#     )

#     # De-duplicate by candidate — keep highest-score resume per candidate
#     seen_candidates: Dict[int, dict] = {}
#     for candidate, resume in results:
#         if candidate.id not in seen_candidates:
#             seen_candidates[candidate.id] = {
#                 "candidate": candidate,
#                 "resume": resume,
#             }

#     documents, metadatas, ids = [], [], []
#     for cand_id, data in seen_candidates.items():
#         c = data["candidate"]
#         r = data["resume"]
#         score = r.final_score or 0.0
#         status = "Accepted" if score >= 6.5 else "Rejected"

#         doc = (
#             f"Candidate Name: {c.name or 'Unknown'}\n"
#             f"Email: {c.email or 'N/A'}\n"
#             f"Mobile: {c.mobile or 'N/A'}\n"
#             f"Skills: {c.skills or 'Not listed'}\n"
#             f"Education: {c.education or 'Unknown'}\n"
#             f"Experience: {c.experience or 'Unknown'} years\n"
#             f"Address: {c.address or 'N/A'}\n"
#             f"Final Score: {score:.2f}/10\n"
#             f"Hiring Status: {status}\n"
#             f"Resume Source: {r.source or 'N/A'}\n"
#             f"Processed At: {r.created_at.strftime('%Y-%m-%d') if r.created_at else 'N/A'}"
#         )
#         documents.append(doc)
#         metadatas.append({
#             "name": c.name or "",
#             "email": c.email or "",
#             "score": score,
#             "status": status,
#             "skills": c.skills or "",
#             "experience": c.experience or "",
#             "address": c.address or "",
#         })
#         ids.append(f"candidate_{cand_id}")

#     return documents, metadatas, ids


# # ─── Build / refresh ChromaDB vectorstore ─────────────────────────────────────

# def build_vectorstore(db: Session):
#     """
#     Builds an in-memory ChromaDB collection from all candidates in the DB.
#     Returns the collection object (or None if no candidates exist).
#     """
#     try:
#         import chromadb
#         from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
#     except ImportError:
#         raise ImportError("chromadb is not installed. Run: pip install chromadb")

#     documents, metadatas, ids = _get_candidate_documents(db)
#     if not documents:
#         return None

#     embedding_fn = SentenceTransformerEmbeddingFunction(
#         model_name="all-MiniLM-L6-v2"
#     )

#     client = chromadb.Client()  # in-memory

#     # Drop old collection if rebuilding
#     try:
#         client.delete_collection("hr_candidates")
#     except Exception:
#         pass

#     collection = client.create_collection(
#         name="hr_candidates",
#         embedding_function=embedding_fn,
#     )
#     collection.add(documents=documents, metadatas=metadatas, ids=ids)
#     return collection


# # ─── RAG Query ────────────────────────────────────────────────────────────────

# def _build_context(collection, question: str, n_results: int = 5) -> str:
#     """Retrieve top-k candidate docs relevant to the question."""
#     results = collection.query(query_texts=[question], n_results=min(n_results, collection.count()))
#     docs = results.get("documents", [[]])[0]
#     if not docs:
#         return "No relevant candidate data found."
#     return "\n\n---\n\n".join(docs)


# def ask_hr_chatbot(question: str, collection, groq_api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
#     """
#     Main RAG function: retrieve relevant candidates → ask Groq LLM.
#     Returns the assistant's answer string.
#     """
#     try:
#         from groq import Groq
#     except ImportError:
#         raise ImportError("groq package not installed. Run: pip install groq")

#     context = _build_context(collection, question)

#     system_prompt = (
#         "You are an intelligent HR assistant. You help HR managers analyze candidate data. "
#         "Answer questions about candidates based ONLY on the data provided below. "
#         "Be concise, factual, and helpful. If the data doesn't contain enough information, say so.\n\n"
#         "CANDIDATE DATA:\n"
#         f"{context}"
#     )

#     client = Groq(api_key=groq_api_key)
#     response = client.chat.completions.create(
#         model=model,
#         messages=[
#             {"role": "system", "content": system_prompt},
#             {"role": "user", "content": question},
#         ],
#         temperature=0.3,
#         max_tokens=800,
#     )
#     return response.choices[0].message.content.strip()


# # ─── Main UI entry point ──────────────────────────────────────────────────────

# def get_chatbot_response(question: str, db: Session) -> str:
#     """
#     High-level function called from main.py.
#     Builds the vectorstore (fresh each call for simplicity) and runs RAG.
#     """
#     groq_api_key = os.getenv("GROQ_API_KEY", "")
#     if not groq_api_key:
#         return "❌ GROQ_API_KEY not found in environment variables."

#     collection = build_vectorstore(db)
#     if collection is None:
#         return "💡 No candidates in the database yet. Process some resumes first, then ask me about them!"

#     try:
#         answer = ask_hr_chatbot(question, collection, groq_api_key)
#         return answer
#     except Exception as e:
#         return f"❌ Error generating response: {str(e)}"




"""
chatbot.py — AI HR Chatbot using RAG (Retrieval-Augmented Generation)
Uses ChromaDB for vector storage + Groq LLM for answering HR questions
based on the candidate data already in the database.
"""

import os
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models import Candidate, Resume


# ─── Build candidate documents ────────────────────────────────────────────────

def _get_candidate_documents(db: Session) -> tuple[List[str], List[dict], List[str]]:
    """
    Pull all candidates + their LATEST resume scores from the DB.
    Returns (documents, metadatas, ids) ready for ChromaDB ingestion.
    """
    results = (
        db.query(Candidate, Resume)
        .join(Resume, Resume.candidate_id == Candidate.id)
        .order_by(Resume.created_at.desc())  # Sort by latest first
        .all()
    )

    # De-duplicate by candidate — keep the LATEST resume per candidate
    seen_candidates: Dict[int, dict] = {}
    for candidate, resume in results:
        if candidate.id not in seen_candidates:
            seen_candidates[candidate.id] = {
                "candidate": candidate,
                "resume": resume,
            }

    documents, metadatas, ids = [], [], []
    for cand_id, data in seen_candidates.items():
        c = data["candidate"]
        r = data["resume"]
        score = r.final_score or 0.0
        
        # Use DB hiring_status if it exists, otherwise fallback to score logic
        status = r.hiring_status
        if not status:
            status = "Accepted" if score >= 6.5 else "Rejected"

        doc = (
            f"Candidate Name: {c.name or 'Unknown'}\n"
            f"Email: {c.email or 'N/A'}\n"
            f"Mobile: {c.mobile or 'N/A'}\n"
            f"Skills: {c.skills or 'Not listed'}\n"
            f"Education: {c.education or 'Unknown'}\n"
            f"Experience: {c.experience or 'Unknown'} years\n"
            f"Address: {c.address or 'N/A'}\n"
            f"Final Score: {score:.2f}/10\n"
            f"Hiring Status: {status}\n"
            f"Resume Source: {r.source or 'N/A'}\n"
            f"Processed At: {r.created_at.strftime('%Y-%m-%d %H:%M:%S') if r.created_at else 'N/A'}"
        )
        documents.append(doc)
        metadatas.append({
            "name": c.name or "",
            "email": c.email or "",
            "score": score,
            "status": status,
            "date": r.created_at.strftime('%Y-%m-%d') if r.created_at else "",
            "skills": c.skills or "",
            "experience": c.experience or "",
            "address": c.address or "",
        })
        ids.append(f"candidate_{cand_id}")

    return documents, metadatas, ids


# ─── Build / refresh ChromaDB vectorstore ─────────────────────────────────────

def ingest_data(db: Session):
    """
    Ingest candidates into a persistent ChromaDB collection.
    """
    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError:
        raise ImportError("chromadb is not installed. Run: pip install chromadb")

    documents, metadatas, ids = _get_candidate_documents(db)
    if not documents:
        return None

    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )

    client = chromadb.PersistentClient(path="./chroma_db")
    
    collection = client.get_or_create_collection(
        name="hr_candidates",
        embedding_function=embedding_fn
    )

    collection.upsert(
        documents=documents,
        metadatas=metadatas,
        ids=ids
    )
    return collection


# ─── RAG Query ────────────────────────────────────────────────────────────────

def _build_context(collection, question: str, n_results: int = 10) -> str:
    """Retrieve top-k candidate docs relevant to the question."""
    results = collection.query(query_texts=[question], n_results=min(n_results, collection.count()))
    docs = results.get("documents", [[]])[0]
    if not docs:
        return "No relevant candidate data found."
    return "\n\n---\n\n".join(docs)


def ask_hr_chatbot(question: str, collection, groq_api_key: str, model: str = "llama-3.3-70b-versatile") -> str:
    """
    Main RAG function: retrieve relevant candidates → ask Groq LLM.
    Returns the assistant's answer string.
    """
    try:
        from groq import Groq
    except ImportError:
        raise ImportError("groq package not installed. Run: pip install groq")

    context = _build_context(collection, question, n_results=10)

    from datetime import datetime
    current_date = datetime.now().strftime("%Y-%m-%d")

    system_prompt = (
        "You are an intelligent HR assistant. You help HR managers analyze candidate data. "
        f"Today's date is {current_date}. "
        "Answer questions about candidates based ONLY on the data provided below. "
        "Pay extremely close attention to the 'Processed At' timestamps and 'Hiring Status'. "
        "If the user asks about 'today' or a specific date, compare it with the 'Processed At' field. "
        "Be concise, factual, and helpful. If the data doesn't contain enough information, say so.\n\n"
        "CANDIDATE DATA:\n"
        f"{context}"
    )

    client = Groq(api_key=groq_api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        temperature=0.1,  # Lower temperature for more factual responses
        max_tokens=1000,
    )
    return response.choices[0].message.content.strip()


# ─── Main UI entry point ──────────────────────────────────────────────────────

cache = {}

def cached_query(question: str, collection, groq_api_key: str) -> str:
    if question in cache:
        return cache[question]

    answer = ask_hr_chatbot(question, collection, groq_api_key)
    cache[question] = answer
    return answer

def get_chatbot_response(question: str, db: Session) -> str:
    """
    High-level function called from main.py.
    Queries the persistent vectorstore and runs RAG.
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "")
    if not groq_api_key:
        return "❌ GROQ_API_KEY not found in environment variables."

    try:
        import chromadb
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError:
        return "❌ chromadb is not installed."

    client = chromadb.PersistentClient(path="./chroma_db")
    embedding_fn = SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    try:
        collection = client.get_collection(name="hr_candidates", embedding_function=embedding_fn)
    except Exception:
        # Collection might not exist yet if ingest_data hasn't been run
        return "💡 No candidates in the database yet. Process some resumes first, then ask me about them!"

    if collection.count() == 0:
        return "💡 No candidates in the database yet. Process some resumes first, then ask me about them!"

    try:
        answer = cached_query(question, collection, groq_api_key)
        return answer
    except Exception as e:
        return f"❌ Error generating response: {str(e)}"
