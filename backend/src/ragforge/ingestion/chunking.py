"""Deterministic, character-offset-preserving document chunking."""

from __future__ import annotations

import hashlib
import re

from ..models import Chunk, Document


def _break_positions(text: str) -> tuple[list[int], list[int]]:
    """Return paragraph boundaries separately from ordinary whitespace."""

    paragraphs = [m.end() for m in re.finditer(r"\n\s*\n+", text)]
    whitespace = [m.end() for m in re.finditer(r"\s+", text)]
    return paragraphs, whitespace


def chunk_document(document: Document, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[Chunk]:
    """Split a document into bounded, overlapping chunks.

    Offsets are Python character offsets and every chunk's text is exactly
    ``document.text[start_char:end_char]``.  Paragraph/whitespace boundaries
    are preferred when they fit; long paragraphs are safely split at the
    configured limit.
    """

    if not isinstance(document, Document):
        raise TypeError("document must be a Document")
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer")
    if not isinstance(chunk_overlap, int) or isinstance(chunk_overlap, bool) or chunk_overlap < 0:
        raise ValueError("chunk_overlap must be a non-negative integer")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")
    text = document.text
    if not isinstance(text, str):
        raise TypeError("document.text must be a string")
    if not text:
        return []

    paragraph_boundaries, whitespace_boundaries = _break_positions(text)
    chunks: list[Chunk] = []
    start = 0
    while start < len(text):
        limit = min(len(text), start + chunk_size)
        # Prefer completing a paragraph over a later ordinary word boundary.
        fitting_paragraphs = [p for p in paragraph_boundaries if start < p <= limit]
        fitting = fitting_paragraphs or [p for p in whitespace_boundaries if start < p <= limit]
        end = max(fitting) if fitting else limit
        # Avoid returning only a boundary's whitespace when a real paragraph
        # boundary is available just before it.
        if end <= start:
            end = limit
        index = len(chunks)
        chunk_text = text[start:end]
        digest = hashlib.sha256(
            f"{document.id}\0{index}\0{start}\0{end}\0".encode("utf-8") + chunk_text.encode("utf-8")
        ).hexdigest()[:24]
        metadata = dict(document.metadata)
        metadata["title"] = document.title
        metadata["document_title"] = document.title
        chunks.append(Chunk(
            id=f"{document.id}:{index}:{digest}",
            document_id=document.id,
            text=chunk_text,
            index=index,
            start_char=start,
            end_char=end,
            metadata=metadata,
        ))
        if end >= len(text):
            break
        next_start = end - chunk_overlap
        # The strict progress guard also handles pathological zero-width
        # boundaries and ensures a malformed input cannot loop forever.
        start = max(start + 1, next_start)
    return chunks
