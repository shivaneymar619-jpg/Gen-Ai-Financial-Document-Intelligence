from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

def split_documents(documents: list[Document], chunk_size: int = 1000, chunk_overlap: int = 200) -> list[Document]:
    """
    Splits the extracted document text into smaller chunks.
    This helps in retrieving granular context and bypassing LLM context window limits.
    
    Args:
        documents (list[Document]): List of documents loaded from the source.
        chunk_size (int): The maximum size of each text chunk.
        chunk_overlap (int): How much overlap between consecutive chunks to preserve meaning.
        
    Returns:
        list[Document]: The resulting smaller chunk documents.
    """
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""]
    )
    
    chunks = text_splitter.split_documents(documents)
    return chunks
