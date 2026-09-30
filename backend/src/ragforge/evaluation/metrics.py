"""Deterministic document-level ranking metrics.

Inputs may be document-id strings, mappings, or ``SearchHit`` instances.  A
hit's ``chunk.document_id`` is used and duplicate chunks count once.  Ties are
ordered by document id (not input or hash iteration order).  Query metrics are
``None`` for missing/empty judgments or no positive relevance.  Macro means
exclude ``None`` values; the report includes both ``evaluated_queries`` and
``unavailable_queries`` so this policy is visible.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def _doc_id(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        for key in ("document_id", "doc_id", "id", "_id"):
            if item.get(key) is not None:
                return str(item[key])
        chunk = item.get("chunk")
        if chunk is not None:
            return _doc_id(chunk)
    chunk = getattr(item, "chunk", None)
    if chunk is not None:
        return str(getattr(chunk, "document_id", getattr(chunk, "id", "")))
    return str(getattr(item, "document_id", getattr(item, "id", item)))


def _score(item: Any) -> float | None:
    if isinstance(item, Mapping):
        value = item.get("score")
    else:
        value = getattr(item, "score", None)
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def ranked_document_ids(ranking: Iterable[Any], k: int | None = None) -> list[str]:
    """Return stable, de-duplicated document ids from a ranking."""
    records = [(_doc_id(x), _score(x), i) for i, x in enumerate(ranking)]
    if any(score is not None for _, score, _ in records):
        records.sort(key=lambda r: (-(r[1] if r[1] is not None else float("-inf")), r[0], r[2]))
    # A score-less sequence is already a ranking; preserve its order.
    seen: set[str] = set()
    result: list[str] = []
    for doc_id, _, _ in records:
        if doc_id and doc_id not in seen:
            seen.add(doc_id)
            result.append(doc_id)
            if k is not None and len(result) >= max(0, k):
                break
    return result


def _judgments(qrels: Mapping[str, Any], query_id: str) -> dict[str, float] | None:
    raw = qrels.get(query_id)
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return {str(k): float(v) for k, v in raw.items() if _number(v)}
    return {str(x): 1.0 for x in raw}


def _number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def recall_at_k(judgments: Mapping[str, Any] | Sequence[Any], ranking: Sequence[Any] | Mapping[str, Any], k: int, query_id: str | None = None) -> float | None:
    """Recall@k for one query, or ``None`` when its gold is unavailable."""
    if not isinstance(judgments, Mapping):  # convenient (retrieved, relevant, k) form
        judgments, ranking = ranking, judgments
    gold = _judgments(judgments, query_id) if query_id is not None else (
        {str(a): float(b) for a, b in judgments.items()} if isinstance(judgments, Mapping) else {str(x): 1.0 for x in judgments}
    )
    if not gold:
        return None
    relevant = {doc for doc, grade in gold.items() if grade > 0}
    if not relevant:
        return None
    return len(relevant.intersection(ranked_document_ids(ranking, k))) / len(relevant)


def mrr_at_k(judgments: Mapping[str, Any] | Sequence[Any], ranking: Sequence[Any] | Mapping[str, Any], k: int, query_id: str | None = None) -> float | None:
    if not isinstance(judgments, Mapping):
        judgments, ranking = ranking, judgments
    gold = _judgments(judgments, query_id) if query_id is not None else ({str(a): float(b) for a, b in judgments.items()} if isinstance(judgments, Mapping) else {str(x): 1.0 for x in judgments})
    if not gold or not any(v > 0 for v in gold.values()):
        return None
    relevant = {doc for doc, grade in gold.items() if grade > 0}
    for position, doc in enumerate(ranked_document_ids(ranking, k), 1):
        if doc in relevant:
            return 1.0 / position
    return 0.0


def ndcg_at_k(judgments: Mapping[str, Any] | Sequence[Any], ranking: Sequence[Any] | Mapping[str, Any], k: int, query_id: str | None = None) -> float | None:
    if not isinstance(judgments, Mapping):
        judgments, ranking = ranking, judgments
    gold = _judgments(judgments, query_id) if query_id is not None else ({str(a): float(b) for a, b in judgments.items()} if isinstance(judgments, Mapping) else {str(x): 1.0 for x in judgments})
    if not gold or not any(v > 0 for v in gold.values()):
        return None
    ids = ranked_document_ids(ranking, k)
    dcg = sum(gold.get(doc, 0.0) / math.log2(position + 2) for position, doc in enumerate(ids))
    ideal = sorted((v for v in gold.values() if v > 0), reverse=True)[:k]
    denom = sum(value / math.log2(position + 2) for position, value in enumerate(ideal))
    return dcg / denom if denom else None


def evaluate_rankings(qrels: Mapping[str, Any], rankings: Mapping[str, Sequence[Any]], ks: Iterable[int] = (1, 3, 5, 10)) -> dict[str, Any]:
    """Evaluate all query rankings and return per-k values plus availability."""
    result: dict[str, Any] = {"averaging": "macro; unavailable query values excluded", "metrics": {}}
    for k in sorted({int(x) for x in ks if int(x) > 0}):
        names = {"recall": [], "mrr": [], "ndcg": []}
        for query_id, ranking in rankings.items():
            names["recall"].append(recall_at_k(qrels, ranking, k, query_id))
            names["mrr"].append(mrr_at_k(qrels, ranking, k, query_id))
            names["ndcg"].append(ndcg_at_k(qrels, ranking, k, query_id))
        result["metrics"][str(k)] = {
            name: (sum(v for v in values if v is not None) / len([v for v in values if v is not None]) if any(v is not None for v in values) else None)
            for name, values in names.items()
        }
        result["metrics"][str(k)]["evaluated_queries"] = sum(v is not None for v in names["recall"])
        result["metrics"][str(k)]["unavailable_queries"] = sum(v is None for v in names["recall"])
    return result
