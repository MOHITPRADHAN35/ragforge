"""Safe, in-memory document ingestion helpers."""

from .parsing import parse_bytes
from .chunking import chunk_document

__all__ = ["parse_bytes", "chunk_document"]
