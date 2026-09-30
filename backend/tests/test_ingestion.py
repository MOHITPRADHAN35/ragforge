import pytest

from ragforge.ingestion import chunk_document, parse_bytes
from ragforge.models import Document


def test_parse_utf8_and_html_strips_active_content():
    assert parse_bytes("note.md", "héllo".encode()) == "héllo"
    assert parse_bytes("page.html", b"<h1>Title</h1><script>bad()</script><p>Hello &amp; world</p>") == "Title\n\nHello & world"


def test_parse_rejects_urls_and_unknown_types():
    with pytest.raises(ValueError, match="URL"):
        parse_bytes("https://example.test/a.txt", b"x")
    with pytest.raises(ValueError, match="unsupported"):
        parse_bytes("data.csv", b"x")


def test_chunk_offsets_overlap_ids_and_title_metadata():
    document = Document("doc-1", "A title", "first paragraph.\n\nsecond paragraph is longer.", {"source": "unit"})
    chunks = chunk_document(document, chunk_size=20, chunk_overlap=5)
    assert chunks
    assert all(chunk.text == document.text[chunk.start_char:chunk.end_char] for chunk in chunks)
    assert all(chunk.end_char > chunk.start_char for chunk in chunks)
    assert all(chunk.metadata["title"] == "A title" for chunk in chunks)
    assert chunks == chunk_document(document, chunk_size=20, chunk_overlap=5)
    assert any(a.end_char > b.start_char for a, b in zip(chunks, chunks[1:]))


def test_chunk_invalid_parameters():
    document = Document("x", "x", "content")
    with pytest.raises(ValueError):
        chunk_document(document, 0)
    with pytest.raises(ValueError):
        chunk_document(document, 2, 2)
