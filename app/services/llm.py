"""
LLM Service
Builds RAG prompts and calls Claude (Anthropic) to generate grounded answers.
"""
from typing import List, Dict, Any, Optional

import anthropic

from app.core.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are a helpful internal knowledge assistant. Your job is to answer employee questions accurately using ONLY the document excerpts provided in the context below.

Rules you MUST follow:
1. Base your answer exclusively on the provided context. Do NOT use external knowledge.
2. If the context does not contain enough information to answer the question, say so clearly — do not guess or fabricate.
3. Always cite the source document(s) you used, referencing them as [Source: <document title>, Page <page>] inline.
4. Be concise and direct. Use bullet points when listing multiple items.
5. If the user's question is ambiguous, briefly clarify what you understood before answering.

You are speaking with an employee who needs accurate, reliable information."""


def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a readable context block for the prompt."""
    if not chunks:
        return "No relevant document excerpts were found."

    parts = []
    for i, chunk in enumerate(chunks, 1):
        title = chunk.get("document_title", "Unknown Document")
        page = chunk.get("page_number") or "N/A"
        content = chunk.get("content", "").strip()
        parts.append(
            f"[Excerpt {i}]\n"
            f"Source: {title}  |  Page: {page}  |  Relevance: {chunk.get('similarity', 0):.0%}\n"
            f"{content}"
        )
    return "\n\n---\n\n".join(parts)


def build_conversation_history(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Convert stored DB messages to Anthropic API message format."""
    return [
        {"role": msg["role"], "content": msg["content"]}
        for msg in messages
        if msg["role"] in ("user", "assistant")
    ]


def generate_answer(
    query: str,
    chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Call Claude with the retrieved context and return the answer + metadata.

    Returns:
        {
          "answer": str,
          "citations": [ { title, filename, page_number, similarity } ],
          "input_tokens": int,
          "output_tokens": int,
        }
    """
    context_block = build_context_block(chunks)

    user_message = (
        f"<context>\n{context_block}\n</context>\n\n"
        f"<question>\n{query}\n</question>"
    )

    # Build message list: prior history + current user message
    messages = []
    if conversation_history:
        messages.extend(build_conversation_history(conversation_history))
    messages.append({"role": "user", "content": user_message})

    response = _client.messages.create(
        model=settings.claude_model,
        max_tokens=settings.max_tokens,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    answer_text = response.content[0].text if response.content else "No response generated."

    # Deduplicate citations
    seen = set()
    citations = []
    for chunk in chunks:
        key = (chunk.get("document_id"), chunk.get("page_number"))
        if key not in seen:
            seen.add(key)
            citations.append({
                "document_title": chunk.get("document_title"),
                "filename": chunk.get("filename"),
                "page_number": chunk.get("page_number"),
                "similarity": chunk.get("similarity"),
            })

    return {
        "answer": answer_text,
        "citations": citations,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
