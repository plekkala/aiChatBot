"""
Retrieval Service
Performs semantic similarity search using pgvector cosine distance.
"""
from typing import List, Dict, Any

from pgvector.sqlalchemy import Vector
from sentence_transformers import SentenceTransformer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DocumentChunk, Document

_embedder = SentenceTransformer("all-MiniLM-L6-v2")


def embed_query(query: str) -> List[float]:
    vector = _embedder.encode([query], normalize_embeddings=True)
    return vector[0].tolist()


def retrieve_relevant_chunks(
    db: Session,
    query: str,
    top_k: int = None,
) -> List[Dict[str, Any]]:
    """
    Returns the top-K most semantically similar document chunks.

    Each result dict contains:
      - chunk_id, document_id, document_title, filename
      - content, page_number, chunk_index
      - similarity score (0-1, higher = more similar)
    """
    top_k = top_k or settings.top_k_results
    query_vector = embed_query(query)

    # pgvector cosine distance: 1 - cosine_similarity
    # We order by distance ASC (smallest distance = most similar)
    sql = text("""
        SELECT
            dc.id            AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            dc.page_number,
            d.filename,
            d.title,
            1 - (dc.embedding <=> CAST(:query_vec AS vector)) AS similarity
        FROM document_chunks dc
        JOIN documents d ON d.id = dc.document_id
        ORDER BY dc.embedding <=> CAST(:query_vec AS vector)
        LIMIT :top_k
    """)

    rows = db.execute(
        sql,
        {
            "query_vec": str(query_vector),
            "top_k": top_k,
        }
    ).fetchall()

    return [
        {
            "chunk_id": str(row.chunk_id),
            "document_id": str(row.document_id),
            "document_title": row.title or row.filename,
            "filename": row.filename,
            "content": row.content,
            "page_number": row.page_number,
            "chunk_index": row.chunk_index,
            "similarity": round(float(row.similarity), 4),
        }
        for row in rows
    ]
