import pytest

from ragforge.models import Chunk, RetrievalOptions
from ragforge.retrieval import HashEmbedder, RetrievalEngine


def chunks():
    return [
        Chunk("a", "one", "Azure deployment guide", 0, 0, 22),
        Chunk("b", "two", "Cooking pasta guide", 0, 0, 19),
        Chunk("c", "one", "Azure monitoring and logs", 1, 23, 48),
    ]


def test_sparse_filter_and_deterministic_scores():
    engine = RetrievalEngine()
    result = engine.search(chunks(), "Azure", RetrievalOptions(mode="sparse", top_k=5, document_ids=["one"]))
    assert [hit.chunk.id for hit in result] == ["a", "c"]
    assert all("sparse" in hit.scores for hit in result)


def test_dense_and_hybrid_keep_raw_components():
    engine = RetrievalEngine()
    dense = engine.search(chunks(), "deployment", RetrievalOptions(mode="dense", top_k=2))
    hybrid = engine.search(chunks(), "deployment", RetrievalOptions(mode="hybrid", top_k=2))
    assert dense and "dense" in dense[0].scores
    assert hybrid and {"sparse", "dense", "rrf"} <= hybrid[0].scores.keys()
    assert hybrid[0].scores["rrf"] == hybrid[0].score


def test_rerank_requires_provider_and_supports_explicit_provider():
    with pytest.raises(ValueError, match="configured reranker"):
        RetrievalEngine().search(chunks(), "guide", RetrievalOptions(rerank=True))

    class Reranker:
        def predict(self, pairs):
            return [1.0 if "pasta" in text else 0.0 for _, text in pairs]

    result = RetrievalEngine(reranker=Reranker()).search(chunks(), "guide", RetrievalOptions(rerank=True, top_k=1))
    assert result[0].chunk.id == "b"
    assert "rerank" in result[0].scores


def test_validation_and_hash_embedder():
    vectors = HashEmbedder(32).embed(["one", "one"])
    assert vectors[0] == vectors[1]
    with pytest.raises(ValueError, match="non-blank"):
        RetrievalEngine().search(chunks(), " ")
    with pytest.raises(ValueError, match="mode"):
        RetrievalEngine().search(chunks(), "x", RetrievalOptions(mode="nope"))
