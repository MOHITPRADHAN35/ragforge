"""Source-tree launcher shim.

This keeps ``python -m ragforge...`` usable from the repository root while
the installable package remains under ``backend/src``.
"""
from pathlib import Path

__path__.append(str(Path(__file__).resolve().parents[1] / "backend" / "src" / "ragforge"))
