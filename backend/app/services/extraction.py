"""Document text extraction: PDF parsing + OCR for images, with graceful fallbacks."""
import os

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    from PIL import Image
    import pytesseract
except Exception:
    Image = None
    pytesseract = None


def extract_pages(file_path: str) -> list[dict]:
    """Return [{'page': int, 'text': str}] for a PDF, image, or text file."""
    ext = os.path.splitext(file_path)[1].lower()
    pages: list[dict] = []

    if ext == ".pdf":
        if pdfplumber is None:
            raise RuntimeError("pdfplumber not installed; cannot parse PDF.")
        with pdfplumber.open(file_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append({"page": i + 1, "text": text})

    elif ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        if pytesseract is None or Image is None:
            raise RuntimeError("pytesseract/Pillow not installed; cannot OCR image.")
        try:
            text = pytesseract.image_to_string(Image.open(file_path)).strip()
        except Exception as e:  # Tesseract binary may be missing on PATH
            raise RuntimeError(f"OCR failed (is the Tesseract binary installed?): {e}")
        if text:
            pages.append({"page": 1, "text": text})

    elif ext in (".txt", ".md", ".csv"):
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        if text.strip():
            pages.append({"page": 1, "text": text})
    else:
        raise ValueError(f"Unsupported file format: {ext}")

    return pages


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Recursive-character-style chunking with overlap (no hard dependency)."""
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=overlap,
            separators=["\n\n", "\n", " ", ""],
        )
        return splitter.split_text(text)
    except Exception:
        # Pure-python sliding window fallback
        chunks, start = [], 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start = end - overlap
            if start < 0:
                start = 0
        return [c for c in chunks if c.strip()]
