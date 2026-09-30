"""Reproducible, offline experiment runner and report persistence."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

from ragforge.models import Chunk, Document, RetrievalOptions, SearchHit
from .loaders import EvaluationDataset, load_dataset
from .metrics import evaluate_rankings

MAX_CONFIG_BYTES = 64_000


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _dataset_hash(path: Path) -> str:
    if path.is_file():
        return sha256_file(path)
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file.relative_to(path)).encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def expand_config_grid(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Expand ``grid`` values into bounded, deterministic experiment configs."""
    base = {k: v for k, v in config.items() if k != "grid"}
    grid = config.get("grid", {}) or {}
    if not isinstance(grid, dict):
        raise ValueError("config.grid must be an object")
    keys = sorted(grid)
    values = [v if isinstance(v, list) else [v] for v in (grid[k] for k in keys)]
    if not keys:
        return [base]
    expanded = []
    for choices in product(*values):
        item = dict(base)
        item.update(dict(zip(keys, choices)))
        expanded.append(item)
    if len(expanded) > 256:
        raise ValueError("configuration grid exceeds 256 combinations")
    return expanded


def _chunks(documents: list[Document], size: int, overlap: int) -> list[Chunk]:
    try:
        from ragforge.ingestion import chunk_document  # type: ignore
        return [chunk for doc in documents for chunk in chunk_document(doc, chunk_size=size, chunk_overlap=overlap)]
    except (ImportError, AttributeError):
        result = []
        for doc in documents:
            step = max(1, size - overlap)
            for index, start in enumerate(range(0, max(1, len(doc.text)), step)):
                text = doc.text[start:start + size]
                if not text:
                    break
                result.append(Chunk(f"{doc.id}#chunk-{index}", doc.id, text, index, start, min(len(doc.text), start + size), dict(doc.metadata)))
        return result


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[\w]+", text.lower()))


def _retrieve(chunks: list[Chunk], query: str, mode: str, top_k: int) -> list[SearchHit]:
    q = _tokens(query)
    scored = []
    for chunk in chunks:
        words = _tokens(chunk.text)
        if mode in {"dense", "hash"}:
            # Deterministic hash-vector proxy. It is not a neural embedding.
            score = sum((hashlib.sha256(word.encode()).digest()[0] % 17) for word in q & words) / max(1, len(q | words))
        else:
            score = len(q & words) / max(1, len(q))
        scored.append(SearchHit(chunk, float(score), {"mode": float(score)}))
    if mode == "hybrid":
        # Sparse lexical score is intentionally the offline hybrid component.
        scored.sort(key=lambda hit: (-hit.score, hit.chunk.document_id, hit.chunk.id))
    else:
        scored.sort(key=lambda hit: (-hit.score, hit.chunk.document_id, hit.chunk.id))
    result, seen = [], set()
    for hit in scored:
        if hit.chunk.document_id not in seen:
            seen.add(hit.chunk.document_id)
            result.append(hit)
            if len(result) >= top_k:
                break
    return result


def _rankings(dataset: EvaluationDataset, config: dict[str, Any]) -> dict[str, list[SearchHit]]:
    size = int(config.get("chunk_size", 1000))
    overlap = int(config.get("chunk_overlap", min(150, max(0, size // 4))))
    top_k = int(config.get("top_k", 10))
    mode = str(config.get("mode", "sparse"))
    if mode not in {"sparse", "dense", "hash", "hybrid"}:
        raise ValueError(f"unsupported mode: {mode}")
    chunks = _chunks(dataset.documents, size, overlap)
    if mode == "hash":
        engine_mode = "dense"
    else:
        engine_mode = mode
    try:
        from ragforge.retrieval import RetrievalEngine
        engine = RetrievalEngine()
        options = RetrievalOptions(mode=engine_mode, top_k=max(top_k, 1), candidate_k=max(top_k * 3, 30), rrf_k=int(config.get("rrf_k", 60)))
        output = {}
        for query_id, query in dataset.queries.items():
            hits = engine.search(chunks, query, options)
            seen, unique = set(), []
            for hit in hits:
                if hit.chunk.document_id not in seen:
                    seen.add(hit.chunk.document_id)
                    unique.append(hit)
            output[query_id] = unique[:top_k]
        return output
    except (ImportError, ValueError, RuntimeError, TypeError):
        return {query_id: _retrieve(chunks, query, mode, top_k) for query_id, query in dataset.queries.items()}


def _safe_report_path(output_dir: Path, run_id: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidate = output_dir / f"report-{run_id}.json"
    suffix = 1
    while candidate.exists():
        candidate = output_dir / f"report-{run_id}-{suffix}.json"
        suffix += 1
    return candidate


def run_custom_experiment(dataset_path: Path, output_dir: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Run local retrieval experiments and persist a never-overwritten report."""
    config_text = _json(config)
    if len(config_text.encode()) > MAX_CONFIG_BYTES:
        raise ValueError(f"configuration exceeds {MAX_CONFIG_BYTES} bytes")
    dataset_path, output_dir = Path(dataset_path).resolve(), Path(output_dir).resolve()
    dataset = load_dataset(dataset_path, split=str(config.get("split", "test")))
    dataset_hash = _dataset_hash(dataset_path)
    configs = expand_config_grid(config)
    reports = []
    for item in configs:
        canonical = _json({"dataset_sha256": dataset_hash, "config": item})
        run_id = hashlib.sha256(canonical.encode()).hexdigest()[:16]
        rankings = _rankings(dataset, item)
        metrics = evaluate_rankings(dataset.qrels, rankings, item.get("ks", [1, 3, 5, 10]))
        reports.append({"run_id": run_id, "config": item, "metrics": metrics, "baseline": "deterministic hash proxy" if item.get("mode") in {"hash", "dense"} else "lexical sparse"})
    report = {"schema_version": 1, "dataset": {"name": dataset.name, "path": str(dataset_path), "sha256": dataset_hash}, "config_sha256": hashlib.sha256(config_text.encode()).hexdigest(), "created_at": datetime.now(timezone.utc).isoformat(), "runs": reports}
    report_path = _safe_report_path(output_dir, reports[0]["run_id"] if reports else hashlib.sha256(config_text.encode()).hexdigest()[:16])
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def load_report(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict) or "runs" not in value:
        raise ValueError("not a ragforge evaluation report")
    return value
