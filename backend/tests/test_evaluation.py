import json
from pathlib import Path

from ragforge.evaluation.generation import evaluate_generation
from ragforge.evaluation.loaders import load_beir, load_custom
from ragforge.evaluation.metrics import evaluate_rankings, mrr_at_k, ndcg_at_k, recall_at_k
from ragforge.evaluation.experiments import run_custom_experiment


def test_metrics_graded_and_document_deduplication():
    qrels = {"q": {"doc-a": 3, "doc-b": 1, "doc-c": 0}}
    ranking = [{"document_id": "doc-a", "score": 1}, {"document_id": "doc-a", "score": .9}, {"document_id": "doc-b", "score": .8}]
    assert recall_at_k(qrels, ranking, 2, "q") == 1.0
    assert mrr_at_k(qrels, ranking, 2, "q") == 1.0
    assert ndcg_at_k(qrels, ranking, 2, "q") == 1.0
    assert recall_at_k(qrels, ["doc-a"], 1, "missing") is None


def test_evaluation_availability_and_beir_ids(tmp_path: Path):
    (tmp_path / "corpus.jsonl").write_text('{"_id":"alpha-x","title":"A","text":"hello"}\n', encoding="utf8")
    (tmp_path / "queries.jsonl").write_text('{"_id":"query-z","text":"hello"}\n', encoding="utf8")
    (tmp_path / "qrels").mkdir()
    (tmp_path / "qrels" / "test.tsv").write_text("query-z\talpha-x\t2\n", encoding="utf8")
    dataset = load_beir(tmp_path)
    assert dataset.queries == {"query-z": "hello"}
    assert dataset.qrels["query-z"]["alpha-x"] == 2
    result = evaluate_rankings(dataset.qrels, {"query-z": ["alpha-x"], "missing": []}, [1])
    assert result["metrics"]["1"]["recall"] == 1.0
    assert result["metrics"]["1"]["unavailable_queries"] == 1


def test_generation_does_not_claim_judge_metrics():
    result = evaluate_generation([{"answer": "Paris", "gold_answer": "Paris", "expected_evidence": ["d1"], "citations": ["d1"]}])
    assert result["metrics"]["answer_lexical_f1"] == 1.0
    assert result["metrics"]["faithfulness"] is None
    assert result["metrics"]["citation_correctness"] is None


def test_experiment_hash_and_never_clobber(tmp_path: Path):
    dataset = tmp_path / "dataset.json"
    dataset.write_text(json.dumps({"documents": [{"id": "d", "text": "alpha text"}], "questions": [{"id": "q", "question": "alpha", "expected_evidence": ["d"]}]}), encoding="utf8")
    first = run_custom_experiment(dataset, tmp_path / "out", {"mode": "hash", "grid": {"chunk_size": [100, 200]}})
    second = run_custom_experiment(dataset, tmp_path / "out", {"mode": "hash", "grid": {"chunk_size": [100, 200]}})
    assert first["dataset"]["sha256"] == second["dataset"]["sha256"]
    assert first["config_sha256"] == second["config_sha256"]
    assert Path(first["report_path"]).exists() and Path(second["report_path"]).exists()
    assert first["report_path"] != second["report_path"]
