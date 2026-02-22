"""
Documents API Router
POST /api/documents          — upload and ingest a document
GET  /api/documents          — list all ingested documents
DELETE /api/documents/{id}   — remove a document and its chunks
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session

from app.db.models import get_db, Document
from app.services.ingestion import ingest_document, SUPPORTED_EXTENSIONS
from pathlib import Path

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    ext = Path(file.filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}"
        )

    file_bytes = await file.read()
    if len(file_bytes) > 50 * 1024 * 1024:  # 50 MB guard
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit.")

    try:
        doc = ingest_document(db, file.filename, file_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "title": doc.title,
        "file_type": doc.file_type,
        "uploaded_at": doc.uploaded_at,
        "chunk_count": len(doc.chunks),
    }


@router.get("")
def list_documents(db: Session = Depends(get_db)):
    docs = db.query(Document).order_by(Document.uploaded_at.desc()).all()
    return [
        {
            "document_id": str(d.id),
            "filename": d.filename,
            "title": d.title,
            "file_type": d.file_type,
            "uploaded_at": d.uploaded_at,
            "chunk_count": len(d.chunks),
        }
        for d in docs
    ]


@router.delete("/{document_id}", status_code=204)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter_by(id=document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    db.delete(doc)
    db.commit()
