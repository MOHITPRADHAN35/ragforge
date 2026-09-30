"""Deterministic retrieval primitives with optional model providers."""

from __future__ import annotations

from collections import Counter
import hashlib
import math
import re
from typing import Any, Callable, Protocol, Sequence

from ..models import Chunk, RetrievalOptions, SearchHit


class Embedder(Protocol):
    """Minimal embedding provider contract used by :class:`RetrievalEngine`."""

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Stable local baseline embedding; it is not a semantic model."""

    def __init__(self, dimensions: int = 256) -> None:
        if not isinstance(dimensions, int) or isinstance(dimensions, bool) or dimensions <= 0:
            raise ValueError("dimensions must be a positive integer")
        self.dimensions = dimensions

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise TypeError("texts must be a list of strings")
        vectors: list[list[float]] = []
        for text in texts:
            if not isinstance(text, str):
                raise TypeError("texts must contain strings")
            vector = [0.0] * self.dimensions
            tokens = _tokens(text)
            # Include unigrams and adjacent word pairs to make this baseline
            # useful for short retrieval queries without using Python's salted hash.
            features = tokens + [f"{a}\x00{b}" for a, b in zip(tokens, tokens[1:])]
            for feature in features:
                digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
                bucket = int.from_bytes(digest[:4], "big") % self.dimensions
                sign = 1.0 if digest[4] & 1 else -1.0
                vector[bucket] += sign
            norm = math.sqrt(sum(value * value for value in vector))
            if norm:
                vector = [value / norm for value in vector]
            vectors.append(vector)
        return vectors


# Friendly explicit alias for callers that want to name the offline choice.
DeterministicHashEmbedder = HashEmbedder


class SentenceTransformerEmbedder:
    """Lazy adapter for a sentence-transformers model.

    Constructing this adapter does not import the optional package or download
    weights.  The model is loaded on the first ``embed`` call only.
    """

    def __init__(self, model_name: str) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("model_name must be a non-blank string")
        self.model_name = model_name
        self._model: Any | None = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise TypeError("texts must be a list of strings")
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError("configured SentenceTransformer requires optional 'sentence-transformers'") from exc
            self._model = SentenceTransformer(self.model_name)
        encoded = self._model.encode(texts, convert_to_numpy=False)
        return [list(map(float, vector)) for vector in encoded]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.casefold(), flags=re.UNICODE)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("embedding dimensions must match")
    aa = math.sqrt(sum(float(x) * float(x) for x in a))
    bb = math.sqrt(sum(float(x) * float(x) for x in b))
    return (sum(float(x) * float(y) for x, y in zip(a, b)) / (aa * bb)) if aa and bb else 0.0


def _bm25(chunks: list[Chunk], query: str) -> dict[str, float]:
    query_terms = _tokens(query)
    corpus = {chunk.id: _tokens(chunk.text) for chunk in chunks}
    n = len(chunks)
    if not n or not query_terms:
        return {chunk.id: 0.0 for chunk in chunks}
    average_length = sum(len(tokens) for tokens in corpus.values()) / n
    average_length = average_length or 1.0
    document_frequency = Counter(term for terms in corpus.values() for term in set(terms))
    scores: dict[str, float] = {}
    for chunk in chunks:
        terms = corpus[chunk.id]
        frequencies = Counter(terms)
        length = len(terms)
        score = 0.0
        for term in query_terms:
            df = document_frequency.get(term, 0)
            if not df:
                continue
            idf = math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            tf = frequencies.get(term, 0)
            if tf:
                score += idf * (tf * 2.5) / (tf + 1.5 * (1.0 - 0.75 + 0.75 * length / average_length))
        scores[chunk.id] = score
    return scores


class RetrievalEngine:
    """Search chunks with BM25, dense cosine, or reciprocal-rank fusion.

    ``embedder`` can be any object implementing ``embed(list[str])``.  By
    default a deterministic hashing embedder is used, requiring no network or
    model download.  A reranker is invoked only when ``options.rerank`` is
    true; a string configures a lazy sentence-transformers CrossEncoder.
    """

    def __init__(self, embedder: Embedder | None = None, reranker: Any | None = None) -> None:
        if isinstance(embedder, str):
            embedder = SentenceTransformerEmbedder(embedder)
        if embedder is not None and not callable(getattr(embedder, "embed", None)):
            raise TypeError("embedder must provide embed(texts: list[str])")
        self.embedder: Embedder = embedder or HashEmbedder()
        self.reranker = reranker
        self._lazy_reranker: Any | None = None

    def search(
        self,
        chunks: list[Chunk],
        query: str,
        options: RetrievalOptions | None = None,
    ) -> list[SearchHit]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-blank string")
        if not isinstance(chunks, list):
            raise TypeError("chunks must be a list")
        if any(not isinstance(chunk, Chunk) for chunk in chunks):
            raise TypeError("chunks must contain Chunk objects")
        opts = options or RetrievalOptions()
        self._validate_options(opts)
        if not chunks:
            return []
        if opts.document_ids is not None:
            allowed = set(opts.document_ids)
            if any(not isinstance(doc_id, str) for doc_id in opts.document_ids):
                raise ValueError("document_ids must contain strings")
            chunks = [chunk for chunk in chunks if chunk.document_id in allowed]
        if not chunks:
            return []

        sparse_scores = _bm25(chunks, query)
        dense_scores: dict[str, float] = {}
        if opts.mode in {"dense", "hybrid"}:
            vectors = self.embedder.embed([chunk.text for chunk in chunks] + [query])
            if not isinstance(vectors, list) or len(vectors) != len(chunks) + 1:
                raise ValueError("embedder returned the wrong number of vectors")
            query_vector = vectors[-1]
            dense_scores = {chunk.id: _cosine(vector, query_vector) for chunk, vector in zip(chunks, vectors[:-1])}

        sparse_rank = self._rank(chunks, sparse_scores)
        dense_rank = self._rank(chunks, dense_scores) if dense_scores else []
        sparse_rank = sparse_rank[:opts.candidate_k]
        dense_rank = dense_rank[:opts.candidate_k]
        if opts.mode == "sparse":
            selected = sparse_rank
        elif opts.mode == "dense":
            selected = dense_rank
        else:
            selected_ids = {chunk.id for chunk in sparse_rank} | {chunk.id for chunk in dense_rank}
            # Fusion uses ranks (not normalized scores), and raw scores remain
            # available to downstream evidence gates in SearchHit.scores.
            sparse_positions = {chunk.id: rank for rank, chunk in enumerate(sparse_rank, 1)}
            dense_positions = {chunk.id: rank for rank, chunk in enumerate(dense_rank, 1)}
            rrf_scores = {
                chunk_id: (1.0 / (opts.rrf_k + sparse_positions[chunk_id]) if chunk_id in sparse_positions else 0.0)
                + (1.0 / (opts.rrf_k + dense_positions[chunk_id]) if chunk_id in dense_positions else 0.0)
                for chunk_id in selected_ids
            }
            selected = sorted((next(chunk for chunk in chunks if chunk.id == chunk_id) for chunk_id in selected_ids), key=lambda c: (-rrf_scores[c.id], c.id))

        rrf_scores = {}
        if opts.mode == "hybrid":
            sparse_positions = {chunk.id: rank for rank, chunk in enumerate(sparse_rank, 1)}
            dense_positions = {chunk.id: rank for rank, chunk in enumerate(dense_rank, 1)}
            rrf_scores = {chunk.id: (1.0 / (opts.rrf_k + sparse_positions[chunk.id]) if chunk.id in sparse_positions else 0.0) + (1.0 / (opts.rrf_k + dense_positions[chunk.id]) if chunk.id in dense_positions else 0.0) for chunk in selected}

        # Hybrid fusion can produce up to 2*candidate_k IDs.  Reranking is
        # intentionally bounded to the candidate window as in the other modes.
        selected = selected[:opts.candidate_k]
        if opts.rerank:
            rerank_scores = self._rerank(query, selected, opts.candidate_k)
            selected = sorted(selected, key=lambda c: (-rerank_scores[c.id], c.id))
        else:
            rerank_scores = {}
        selected = selected[:opts.top_k]
        hits: list[SearchHit] = []
        for chunk in selected:
            component_scores: dict[str, float] = {}
            if opts.mode in {"sparse", "hybrid"}:
                component_scores["sparse"] = sparse_scores.get(chunk.id, 0.0)
            if opts.mode in {"dense", "hybrid"}:
                component_scores["dense"] = dense_scores.get(chunk.id, 0.0)
            if opts.mode == "hybrid":
                component_scores["rrf"] = rrf_scores.get(chunk.id, 0.0)
            if opts.rerank:
                component_scores["rerank"] = rerank_scores[chunk.id]
            if opts.rerank:
                final_score = rerank_scores[chunk.id]
            elif opts.mode == "hybrid":
                final_score = rrf_scores[chunk.id]
            elif opts.mode == "dense":
                final_score = dense_scores[chunk.id]
            else:
                final_score = sparse_scores[chunk.id]
            hits.append(SearchHit(chunk=chunk, score=final_score, scores=component_scores))
        return hits

    @staticmethod
    def _validate_options(options: RetrievalOptions) -> None:
        if not isinstance(options, RetrievalOptions):
            raise TypeError("options must be RetrievalOptions or None")
        if options.mode not in {"sparse", "dense", "hybrid"}:
            raise ValueError("mode must be 'sparse', 'dense', or 'hybrid'")
        for name in ("top_k", "candidate_k", "rrf_k"):
            value = getattr(options, name)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if options.document_ids is not None and not isinstance(options.document_ids, list):
            raise TypeError("document_ids must be a list of strings or None")
        if not isinstance(options.rerank, bool):
            raise TypeError("rerank must be a boolean")

    @staticmethod
    def _rank(chunks: list[Chunk], scores: dict[str, float]) -> list[Chunk]:
        return sorted(chunks, key=lambda chunk: (-scores.get(chunk.id, 0.0), chunk.id))

    def _get_reranker(self) -> Any:
        if self.reranker is None:
            raise ValueError("rerank=True requires a configured reranker provider")
        if isinstance(self.reranker, str):
            if self._lazy_reranker is None:
                try:
                    from sentence_transformers import CrossEncoder
                except ImportError as exc:
                    raise RuntimeError("configured CrossEncoder reranker requires optional 'sentence-transformers'") from exc
                self._lazy_reranker = CrossEncoder(self.reranker)
            return self._lazy_reranker
        return self.reranker

    def _rerank(self, query: str, chunks: list[Chunk], candidate_k: int) -> dict[str, float]:
        provider = self._get_reranker()
        pairs = [(query, chunk.text) for chunk in chunks[:candidate_k]]
        if callable(getattr(provider, "predict", None)):
            values = provider.predict(pairs)
        elif callable(getattr(provider, "score", None)):
            values = [provider.score(query, chunk.text) for chunk in chunks[:candidate_k]]
        elif callable(provider):
            values = provider(pairs)
        else:
            raise TypeError("reranker must provide predict, score, or be callable")
        try:
            values = list(values)
        except TypeError as exc:
            raise ValueError("reranker must return one score per candidate") from exc
        if len(values) != len(pairs):
            raise ValueError("reranker returned the wrong number of scores")
        try:
            return {chunk.id: float(value) for chunk, value in zip(chunks[:candidate_k], values)}
        except (TypeError, ValueError) as exc:
            raise ValueError("reranker scores must be numeric") from exc
