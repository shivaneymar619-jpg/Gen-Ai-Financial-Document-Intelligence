import os
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from .embeddings import get_embeddings_model

# Global instance for the Streamlit app
_vector_store = None

def get_vector_store() -> InMemoryVectorStore:
    """
    Initializes and returns the in-memory vector database.
    """
    global _vector_store
    if _vector_store is None:
        embeddings = get_embeddings_model()
        _vector_store = InMemoryVectorStore(embeddings)
    
    return _vector_store

def add_documents_to_store(chunks: list[Document]):
    """
    Adds newly chunked documents to the in-memory vector store.
    """
    vector_store = get_vector_store()
    vector_store.add_documents(documents=chunks)
