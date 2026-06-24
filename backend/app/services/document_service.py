"""Document ingestion pipeline: extract -> chunk -> embed -> persist."""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..config import settings
from . import extraction, rag_service


def process_document(db: Session, document_id: str):
    """Run the full ingestion pipeline for one document. Idempotent-ish:
    clears any existing chunks first. Updates status as it goes."""
    doc = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not doc:
        return
    doc.status = "processing"
    db.commit()

    try:
        pages = extraction.extract_pages(doc.storage_path)
        if not pages:
            raise RuntimeError("No extractable text found in document.")

        # Clear prior chunks (reprocess safety)
        db.query(models.DocumentChunk).filter(
            models.DocumentChunk.document_id == doc.id
        ).delete()
        db.commit()

        all_chunks: list[models.DocumentChunk] = []
        texts_for_embedding: list[str] = []

        for page in pages:
            chunks = extraction.chunk_text(
                page["text"], settings.CHUNK_SIZE, settings.CHUNK_OVERLAP
            )
            for idx, content in enumerate(chunks):
                ch = models.DocumentChunk(
                    document_id=doc.id,
                    owner_id=doc.owner_id,
                    page=page["page"],
                    chunk_index=idx,
                    content=content,
                )
                all_chunks.append(ch)
                texts_for_embedding.append(content)

        # Optional embeddings (Gemini). None -> TF-IDF retrieval at query time.
        vectors = rag_service.embed_texts(texts_for_embedding)
        if vectors is not None and len(vectors) == len(all_chunks):
            for ch, vec in zip(all_chunks, vectors):
                ch.embedding = list(map(float, vec))

        db.add_all(all_chunks)

        doc.pages = len(pages)
        doc.chunk_count = len(all_chunks)
        doc.status = "ready"
        doc.processed_at = datetime.now(timezone.utc)
        doc.error = None
        db.commit()

    except Exception as e:
        db.rollback()
        doc = db.query(models.Document).filter(models.Document.id == document_id).first()
        if doc is None:
            return  # document deleted between start and failure — nothing to update
        doc.status = "failed"
        doc.error = str(e)[:500]
        db.commit()
