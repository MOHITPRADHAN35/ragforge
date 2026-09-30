"""Framework-independent contracts shared across the backend."""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Document:
    id: str
    title: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Chunk:
    id: str
    document_id: str
    text: str
    index: int
    start_char: int
    end_char: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    chunk: Chunk
    score: float
    scores: dict[str, float] = field(default_factory=dict)


@dataclass
class RetrievalOptions:
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    top_k: int = 5
    candidate_k: int = 30
    rrf_k: int = 60
    rerank: bool = False
    document_ids: list[str] | None = None


@dataclass
class Citation:
    label: str
    chunk_id: str
    document_id: str
    title: str
    quote: str
    start_char: int
    end_char: int


@dataclass
class Answer:
    question: str
    answer: str
    abstained: bool
    reason: str | None
    citations: list[Citation] = field(default_factory=list)
    hits: list[SearchHit] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)
