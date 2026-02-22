"""
Basic tests for the POC — run with:   pytest tests/ -v
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.ingestion import chunk_text, embed_texts, extract_text_from_txt


def test_chunk_text_basic():
    text = "Hello world. " * 100
    chunks = chunk_text(text)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c) <= 600  # allow a bit of slack around chunk_size


def test_embed_texts_shape():
    texts = ["This is a test sentence.", "Another sentence here."]
    vectors = embed_texts(texts)
    assert len(vectors) == 2
    assert len(vectors[0]) == 384  # all-MiniLM-L6-v2


def test_extract_txt():
    content = b"Hello, this is a plain text document.\nIt has two lines."
    pages = extract_text_from_txt(content)
    assert len(pages) == 1
    page_num, text = pages[0]
    assert page_num == 1
    assert "plain text document" in text
