import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings

def get_embeddings_model():
    """
    Returns the embedding model to be used by the vector store.
    Uses Google's embedding-001 as the default.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables.")
        
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001", 
        google_api_key=api_key
    )
    return embeddings

