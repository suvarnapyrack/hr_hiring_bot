from langchain_openai import OpenAIEmbeddings
import chromadb

# Create / Load vector DB collection
chroma_client = chromadb.Client()
resume_collection = chroma_client.get_or_create_collection("resumes")

embedding_model = OpenAIEmbeddings()

# Store resume in vector DB
def store_resume_vector(resume_id, resume_text, metadata):
    vector = embedding_model.embed_query(resume_text)
    resume_collection.add(
        ids=[resume_id],
        documents=[resume_text],
        embeddings=[vector],
        metadatas=[metadata]
    )

# Search resumes similar to job description
def search_similar_resumes(jd_text, top_k=5):
    jd_vector = embedding_model.embed_query(jd_text)
    results = resume_collection.query(
        query_embeddings=[jd_vector],
        n_results=top_k
    )
    return results
