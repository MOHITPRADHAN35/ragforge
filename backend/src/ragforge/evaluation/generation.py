"""Generation evaluation with explicitly honest metric availability.

String overlap is a lexical proxy, not a faithfulness or semantic relevance
claim.  Faithfulness, answer relevance, and citation correctness remain null
unless a caller supplies a judge callable or gold labels.
"""
from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from typing import Any


def _tokens(value: Any) -> set[str]:
    return set(re.findall(r"[\w]+", str(value or "").lower()))


def _macro(values: Iterable[float | None]) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def evaluate_generation(records: Iterable[Mapping[str, Any]], judge: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Evaluate answer records, returning null for unavailable signals.

    Record keys accepted: ``answer``, ``gold_answer``, ``expected_evidence``,
    ``citations`` (IDs or citation objects), ``abstained``, and
    ``gold_abstained``. A judge may return faithfulness/relevance/citation
    correctness values for a record; it is never invoked over the network.
    """
    rows = list(records)
    metric_values: dict[str, list[float | None]] = {"answer_lexical_f1": [], "evidence_overlap": [], "citation_precision": [], "citation_recall": [], "abstention_accuracy": [], "faithfulness": [], "answer_relevance": [], "citation_correctness": []}
    for row in rows:
        answer, gold = _tokens(row.get("answer")), _tokens(row.get("gold_answer", row.get("reference_answer")))
        if gold:
            overlap = len(answer & gold)
            metric_values["answer_lexical_f1"].append((2 * overlap / (len(answer) + len(gold))) if answer else 0.0)
        else:
            metric_values["answer_lexical_f1"].append(None)
        expected = {str(x.get("document_id", x.get("doc_id", x.get("id", x)))) if isinstance(x, Mapping) else str(x) for x in (row.get("expected_evidence") or [])}
        cited = {str(x.get("document_id", x.get("doc_id", x.get("id", x)))) if isinstance(x, Mapping) else str(x) for x in (row.get("citations") or [])}
        if expected:
            metric_values["evidence_overlap"].append(len(expected & cited) / len(expected))
            metric_values["citation_recall"].append(len(expected & cited) / len(expected))
            metric_values["citation_precision"].append(len(expected & cited) / len(cited) if cited else 0.0)
        else:
            metric_values["evidence_overlap"].append(None)
            metric_values["citation_recall"].append(None)
            metric_values["citation_precision"].append(None)
        if "gold_abstained" in row or "expected_abstain" in row:
            expected_abstain = bool(row.get("gold_abstained", row.get("expected_abstain")))
            metric_values["abstention_accuracy"].append(float(bool(row.get("abstained", False)) == expected_abstain))
        else:
            metric_values["abstention_accuracy"].append(None)
        judged = judge(row) if judge is not None else {}
        for name in ("faithfulness", "answer_relevance", "citation_correctness"):
            value = judged.get(name) if isinstance(judged, Mapping) else None
            try:
                metric_values[name].append(float(value) if value is not None else None)
            except (TypeError, ValueError):
                metric_values[name].append(None)
    metrics = {name: _macro(values) for name, values in metric_values.items()}
    return {
        "metrics": metrics,
        "availability": {name: {"available": sum(v is not None for v in values), "unavailable": sum(v is None for v in values)} for name, values in metric_values.items()},
        "notes": {"answer_lexical_f1": "lexical proxy only; not semantic correctness", "evidence_overlap": "document-id gold overlap, not faithfulness", "faithfulness": "requires external judge; null when no judge supplied", "answer_relevance": "requires external judge; null when no judge supplied", "citation_correctness": "requires external judge or labels; null otherwise", "averaging": "macro over available records; unavailable values excluded"},
        "judge_protocol": "An optional local callable receives one record and returns numeric faithfulness, answer_relevance, and/or citation_correctness fields. An adapter may invoke an external judge, but networking is intentionally not performed by this library.",
        "judge": "external callable" if judge is not None else None,
    }
