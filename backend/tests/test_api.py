from fastapi.testclient import TestClient

from ragforge.api.app import create_app
from ragforge.core.settings import Settings


def client(tmp_path, key=None):
    return TestClient(create_app(Settings(database_path=str(tmp_path / "api.db"), api_key=key)))


def test_auth_and_text_persistence(tmp_path):
    c = client(tmp_path, "secret")
    assert c.get("/api/v1/documents").status_code == 401
    response = c.post("/api/v1/documents/text", headers={"X-API-Key": "secret"}, json={"title": "A", "text": "alpha evidence"})
    assert response.status_code == 200
    assert c.get("/api/v1/documents", headers={"X-API-Key": "secret"}).json()[0]["title"] == "A"


def test_query_citations_and_abstention(tmp_path):
    c = client(tmp_path)
    c.post("/api/v1/documents/text", json={"title": "A", "text": "alpha evidence"})
    answer = c.post("/api/v1/query", json={"query": "alpha", "top_k": 2}).json()
    assert answer["abstained"] is False
    assert answer["citations"][0]["label"] == "[C1]"
    no = c.post("/api/v1/query", json={"query": "zebra", "top_k": 2}).json()
    assert no["abstained"] is True


def test_rewrite_requires_provider(tmp_path):
    c = client(tmp_path)
    assert c.post("/api/v1/query", json={"query": "q", "rewrite": True}).status_code == 422
