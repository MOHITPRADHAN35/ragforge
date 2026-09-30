from typing import Any, Literal
from pydantic import BaseModel, Field


class TextDocumentIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalIn(BaseModel):
    query: str = Field(min_length=1, max_length=10000)
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=100)
    candidate_k: int = Field(default=30, ge=1, le=200)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    rerank: bool = False
    document_ids: list[str] | None = None


class RetrievalConfig(BaseModel):
    mode: Literal["sparse", "dense", "hybrid"] = "hybrid"
    top_k: int = Field(default=5, ge=1, le=100)
    candidate_k: int = Field(default=30, ge=1, le=200)
    rrf_k: int = Field(default=60, ge=1, le=1000)
    rerank: bool = False
    document_ids: list[str] | None = None


class QueryIn(RetrievalIn):
    # Nested form is convenient for clients while flattened fields remain backwards compatible.
    retrieval: RetrievalConfig | None = None
    rewrite: bool = False
    hyde: bool = False
    compress: bool = True


def document_view(d):
    return {"id": d.id, "title": d.title, "text": d.text, "metadata": d.metadata}


def hit_view(h):
    return {"chunk": {"id": h.chunk.id, "document_id": h.chunk.document_id, "text": h.chunk.text, "index": h.chunk.index, "start_char": h.chunk.start_char, "end_char": h.chunk.end_char}, "score": h.score, "scores": h.scores}


def answer_view(a):
    limitation = a.diagnostics.get("limitation") if isinstance(a.diagnostics, dict) else None
    return {
        "question": a.question,
        "answer": a.answer,
        "abstained": a.abstained,
        "reason": a.reason,
        "abstention_reason": a.reason,
        "citations": [
            {
                "label": c.label,
                "chunk_id": c.chunk_id,
                "document_id": c.document_id,
                "title": c.title,
                "quote": c.quote,
                "excerpt": c.quote,
                "start_char": c.start_char,
                "end_char": c.end_char,
            }
            for c in a.citations
        ],
        "hits": [hit_view(h) for h in a.hits],
        "diagnostics": a.diagnostics,
        "limitations": [limitation] if limitation else [],
    }

