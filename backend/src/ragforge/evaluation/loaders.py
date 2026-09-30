"""Local BEIR and small JSON fixture loaders."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ragforge.models import Document


@dataclass
class EvaluationDataset:
    documents: list[Document] = field(default_factory=list)
    queries: dict[str, str] = field(default_factory=dict)
    qrels: dict[str, dict[str, float]] = field(default_factory=dict)
    questions: list[dict[str, Any]] = field(default_factory=list)
    name: str = "dataset"
    source: str | None = None


def _line_json(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
    return rows


def load_beir(path: str | Path, split: str = "test") -> EvaluationDataset:
    """Load a local BEIR directory without downloading or numeric-ID assumptions."""
    root = Path(path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(root)
    corpus_path, queries_path = root / "corpus.jsonl", root / "queries.jsonl"
    if not corpus_path.exists() or not queries_path.exists():
        raise ValueError(f"BEIR directory must contain corpus.jsonl and queries.jsonl: {root}")
    documents = []
    for row in _line_json(corpus_path):
        doc_id = str(row.get("_id", row.get("id", "")))
        if not doc_id:
            raise ValueError("BEIR corpus row has no _id")
        documents.append(Document(id=doc_id, title=str(row.get("title", "")), text=str(row.get("text", "")), metadata={k: v for k, v in row.items() if k not in {"_id", "id", "title", "text"}}))
    queries = {}
    for row in _line_json(queries_path):
        query_id = str(row.get("_id", row.get("id", "")))
        if not query_id:
            raise ValueError("BEIR query row has no _id")
        queries[query_id] = str(row.get("text", row.get("query", "")))
    qrels_dir = root / "qrels"
    qrels_path = qrels_dir / f"{split}.tsv"
    qrels: dict[str, dict[str, float]] = {}
    if qrels_path.exists():
        with qrels_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                # BEIR publishes TSV, while some local mirrors use spaces.
                parts = line.strip().split()
                if not parts or not parts[0] or parts[0].lower() in {"query-id", "query_id"}:
                    continue
                if len(parts) < 3:
                    raise ValueError(f"invalid qrels row at {qrels_path}:{line_number}")
                qrels.setdefault(str(parts[0]), {})[str(parts[1])] = float(parts[-1])
    return EvaluationDataset(documents, queries, qrels, name=root.name, source=str(root))


def load_custom(path: str | Path) -> EvaluationDataset:
    """Load JSON fixtures with documents and questions/expected evidence."""
    file_path = Path(path).resolve()
    with file_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        payload = {"questions": payload}
    documents = []
    for row in payload.get("documents", []):
        if isinstance(row, str):
            row = {"id": row, "text": row}
        doc_id = str(row.get("id", row.get("_id", "")))
        if not doc_id:
            raise ValueError("custom document has no id")
        documents.append(Document(doc_id, str(row.get("title", "")), str(row.get("text", "")), dict(row.get("metadata", {}))))
    questions = payload.get("questions", payload.get("queries", []))
    queries: dict[str, str] = {}
    qrels: dict[str, dict[str, float]] = {}
    normalized: list[dict[str, Any]] = []
    for index, row in enumerate(questions):
        if isinstance(row, str):
            row = {"id": str(index), "question": row}
        query_id = str(row.get("id", row.get("_id", index)))
        question = str(row.get("question", row.get("text", row.get("query", ""))))
        queries[query_id] = question
        evidence = row.get("expected_evidence", row.get("evidence", [])) or []
        evidence_ids = [str(x.get("document_id", x.get("doc_id", x.get("id", x)))) if isinstance(x, dict) else str(x) for x in evidence]
        qrels[query_id] = {doc_id: 1.0 for doc_id in evidence_ids}
        normalized.append({**row, "id": query_id, "question": question, "expected_evidence": evidence_ids})
    # Explicit qrels support graded custom fixtures and are merged with evidence.
    for query_id, values in payload.get("qrels", {}).items():
        qrels[str(query_id)] = {str(doc): float(grade) for doc, grade in values.items()}
    return EvaluationDataset(documents, queries, qrels, normalized, name=str(payload.get("name", file_path.stem)), source=str(file_path))


def load_dataset(path: str | Path, split: str = "test") -> EvaluationDataset:
    path = Path(path)
    if path.is_dir():
        return load_beir(path, split=split)
    return load_custom(path)
