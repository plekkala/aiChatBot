"""
Chat API Router
POST /api/chat        — ask a question, get an answer
GET  /api/chat/{id}  — retrieve conversation history
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import get_db, Conversation, Message
from app.services.retrieval import retrieve_relevant_chunks
from app.services.llm import generate_answer

router = APIRouter(prefix="/api/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class CitationOut(BaseModel):
    document_title: str
    filename: str
    page_number: Optional[int]
    similarity: float


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    citations: list[CitationOut]
    input_tokens: int
    output_tokens: int


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)):
    # ── 1. Load or create conversation ──────────────────────────────────
    if req.conversation_id:
        conv = db.query(Conversation).filter_by(id=req.conversation_id).first()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found.")
    else:
        conv = Conversation(title=req.message[:60])
        db.add(conv)
        db.flush()

    # ── 2. Retrieve relevant chunks ──────────────────────────────────────
    chunks = retrieve_relevant_chunks(db, req.message)

    # ── 3. Build conversation history for multi-turn context ─────────────
    history = [
        {"role": m.role, "content": m.content}
        for m in conv.messages
    ]

    # ── 4. Generate answer via Claude ────────────────────────────────────
    result = generate_answer(req.message, chunks, conversation_history=history)

    # ── 5. Persist messages ───────────────────────────────────────────────
    db.add(Message(conversation_id=conv.id, role="user",      content=req.message))
    db.add(Message(conversation_id=conv.id, role="assistant", content=result["answer"]))
    db.commit()

    return ChatResponse(
        answer=result["answer"],
        conversation_id=str(conv.id),
        citations=result["citations"],
        input_tokens=result["input_tokens"],
        output_tokens=result["output_tokens"],
    )


@router.get("/{conversation_id}")
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter_by(id=conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {
        "conversation_id": str(conv.id),
        "title": conv.title,
        "created_at": conv.created_at,
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at}
            for m in conv.messages
        ],
    }
