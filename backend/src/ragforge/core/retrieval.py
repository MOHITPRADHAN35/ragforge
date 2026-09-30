"""Adapter around the retrieval component, with a deterministic lexical fallback."""
from __future__ import annotations
import re
import importlib
from ragforge.models import Chunk, SearchHit, RetrievalOptions


def _lexical(chunks: list[Chunk], query: str, options: RetrievalOptions) -> list[SearchHit]:
    terms = set(re.findall(r"[\w]+", query.lower()))
    scored = []
    for c in chunks:
        words = re.findall(r"[\w]+", c.text.lower())
        overlap = len(terms & set(words))
        score = overlap / max(1, len(terms))
        if overlap:
            scored.append(SearchHit(c, score, {"lexical": score, "component": score}))
    return sorted(scored, key=lambda x: x.score, reverse=True)[: options.top_k]


def _load(spec: str | None):
    """Load an explicitly configured component only; defaults never import optional ML packages."""
    if not spec:
        return None
    module_name, separator, attr = spec.partition(":")
    if not separator:
        module_name, _, attr = spec.rpartition(".")
    if not module_name or not attr:
        raise ValueError("component must be module:attribute")
    return getattr(importlib.import_module(module_name), attr)


def retrieve(chunks: list[Chunk], query: str, options: RetrievalOptions, embedder=None, reranker=None, *, embedder_spec: str | None = None, reranker_spec: str | None = None) -> list[SearchHit]:
    embedder = embedder if embedder is not None else _load(embedder_spec)
    reranker = reranker if reranker is not None else _load(reranker_spec)
    try:
        from ragforge.retrieval import RetrievalEngine  # type: ignore
        return RetrievalEngine(embedder=embedder, reranker=reranker).search(chunks, query, options)
    except (ImportError, AttributeError):
        return _lexical(chunks, query, options)
