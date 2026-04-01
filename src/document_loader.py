import os
import pdfplumber
from langchain_core.documents import Document
from .ocr_utils import perform_ocr

def load_documents(file_path: str) -> list[Document]:
    """
    Loads text from a PDF or Image file. Returns a list of Langchain Document objects.
    Each Document corresponds to a single page (for PDFs) to retain page metadata.
    
    Args:
        file_path (str): Path to the uploaded document.
        
    Returns:
        list[Document]: List of documents with extracted text and metadata (source, page).
    """
    documents = []
    
    file_ext = os.path.splitext(file_path)[1].lower()
    source_name = os.path.basename(file_path)
    
    if file_ext == '.pdf':
        try:
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    # Extract text directly from PDF
                    text = page.extract_text()
                    
                    # If page is essentially an image, no text might be returned
                    if not text or len(text.strip()) < 10:
                        # Alternatively, we could convert PDF page to image and run OCR
                        # This simple implementation assumes standard PDFs or text-based PDFs
                        pass
                        
                    if text:
                        doc = Document(
                            page_content=text,
                            metadata={"source": source_name, "page": i + 1}
                        )
                        documents.append(doc)
        except Exception as e:
            print(f"Error loading PDF {file_path}: {e}")
            
    elif file_ext in ['.png', '.jpg', '.jpeg']:
        # For an image (like a scanned invoice), we use OCR
        text = perform_ocr(file_path)
        if text:
            doc = Document(
                page_content=text,
                metadata={"source": source_name, "page": 1}
            )
            documents.append(doc)
    else:
        raise ValueError(f"Unsupported file format: {file_ext}")
        
    return documents
