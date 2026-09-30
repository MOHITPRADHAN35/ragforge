"""Offline retrieval and generation evaluation utilities.

The package deliberately has no network or model dependency.  A metric is
``None`` when it cannot be computed (for example, missing gold judgments);
macro averages exclude those queries and expose their count in reports.
"""

from .metrics import evaluate_rankings, mrr_at_k, ndcg_at_k, recall_at_k
from .loaders import EvaluationDataset, load_beir, load_dataset
from .experiments import load_report, run_custom_experiment

__all__ = [
    "EvaluationDataset", "load_beir", "load_dataset", "recall_at_k",
    "mrr_at_k", "ndcg_at_k", "evaluate_rankings", "run_custom_experiment",
    "load_report",
]
