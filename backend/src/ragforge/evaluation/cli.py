"""Command line entry point for offline evaluation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiments import run_custom_experiment


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run deterministic local RAG retrieval benchmarks (no downloads).")
    parser.add_argument("dataset", nargs="?", help="custom JSON fixture or local BEIR directory")
    parser.add_argument("--output-dir", default="evaluation-reports")
    parser.add_argument("--mode", choices=("sparse", "dense", "hash", "hybrid"), default="sparse")
    parser.add_argument("--chunk-size", type=int, nargs="+", default=[1000], help="one or more chunk sizes for comparison")
    parser.add_argument("--chunk-overlap", type=int, default=150)
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--split", default="test")
    args = parser.parse_args(argv)
    if not args.dataset:
        parser.print_help()
        return 0
    # Keep every requested comparison valid when a small chunk size is used.
    overlap = min(args.chunk_overlap, max(0, min(args.chunk_size) - 1))
    config = {"mode": args.mode, "chunk_overlap": overlap, "top_k": args.top_k, "split": args.split, "grid": {"chunk_size": args.chunk_size}}
    report = run_custom_experiment(Path(args.dataset), Path(args.output_dir), config)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
