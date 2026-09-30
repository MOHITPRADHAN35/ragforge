import io
import pytest
from fastapi.testclient import TestClient

from ragforge.api.app import create_app
from ragforge.core.settings import Settings


@pytest.fixture
def app_client(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "test.db"),
        max_top_k=20,
        max_input_chars=5000,
        max_upload_bytes=10000,
    )
    return TestClient(create_app(settings))


@pytest.fixture
def auth_client(tmp_path):
    settings = Settings(
        database_path=str(tmp_path / "auth_test.db"),
        api_key="super-secret-key-123",
    )
    return TestClient(create_app(settings))


class TestHealthAndReadiness:
    def test_health_routes(self, app_client):
        for route in ["/health", "/api/v1/health"]:
            res = app_client.get(route)
            assert res.status_code == 200
            assert res.json()["status"] == "ok"

    def test_ready_routes(self, app_client):
        for route in ["/ready", "/readiness", "/api/v1/ready", "/api/v1/readiness"]:
            res = app_client.get(route)
            assert res.status_code == 200
            assert res.json()["status"] == "ready"

    def test_capabilities(self, app_client):
        res = app_client.get("/api/v1/capabilities")
        assert res.status_code == 200
        data = res.json()
        assert "retrieval_modes" in data
        assert "default_retrieval_mode" in data
        assert data["database"] == "sqlite"


class TestDocumentIngestionAndValidation:
    def test_text_validation_empty(self, app_client):
        # Empty title or text rejected by Pydantic validation
        res = app_client.post("/api/v1/documents/text", json={"title": "", "text": "valid"})
        assert res.status_code == 422
        res2 = app_client.post("/api/v1/documents/text", json={"title": "valid", "text": ""})
        assert res2.status_code == 422

    def test_text_exceeds_max_input_chars(self, app_client):
        oversized_text = "x" * 6000
        res = app_client.post("/api/v1/documents/text", json={"title": "Big", "text": oversized_text})
        assert res.status_code == 413

    def test_upload_file_exceeds_max_upload_bytes(self, app_client):
        large_file = io.BytesIO(b"A" * 15000)
        res = app_client.post(
            "/api/v1/documents/upload",
            files={"file": ("large.txt", large_file, "text/plain")},
        )
        assert res.status_code == 413

    def test_upload_file_types(self, app_client):
        # .txt upload
        res_txt = app_client.post(
            "/api/v1/documents/upload?title=CustomText",
            files={"file": ("sample.txt", io.BytesIO(b"Hello world from text file"), "text/plain")},
        )
        assert res_txt.status_code == 200
        assert res_txt.json()["title"] == "CustomText"
        assert res_txt.json()["chunk_count"] >= 1

        # .md upload without explicit title query parameter -> should fall back to filename
        res_md = app_client.post(
            "/api/v1/documents/upload",
            files={"file": ("guide.md", io.BytesIO(b"# Markdown Title\nSome content here"), "text/markdown")},
        )
        assert res_md.status_code == 200
        assert res_md.json()["title"] == "guide.md"

        # .html upload
        res_html = app_client.post(
            "/api/v1/documents/upload",
            files={"file": ("page.html", io.BytesIO(b"<html><body><p>HTML content</p></body></html>"), "text/html")},
        )
        assert res_html.status_code == 200

    def test_unicode_and_emojis(self, app_client):
        unicode_title = "量子计算 🚀 Über & naïve"
        unicode_text = "Quantum computing uses qubits (量子比特). 🔬 Highlights: 100% precision."
        res = app_client.post("/api/v1/documents/text", json={"title": unicode_title, "text": unicode_text, "metadata": {"lang": "multi"}})
        assert res.status_code == 200
        doc_id = res.json()["id"]

        fetched = app_client.get(f"/api/v1/documents/{doc_id}").json()
        assert fetched["title"] == unicode_title
        assert fetched["text"] == unicode_text


class TestDocumentCRUDAndIntegrity:
    def test_get_nonexistent_document(self, app_client):
        res = app_client.get("/api/v1/documents/non-existent-uuid-999")
        assert res.status_code == 404

    def test_delete_nonexistent_document(self, app_client):
        res = app_client.delete("/api/v1/documents/non-existent-uuid-999")
        assert res.status_code == 404

    def test_cascade_deletion(self, app_client):
        res = app_client.post("/api/v1/documents/text", json={"title": "To Delete", "text": "temporary content"})
        doc_id = res.json()["id"]
        assert len(app_client.get("/api/v1/documents").json()) == 1

        del_res = app_client.delete(f"/api/v1/documents/{doc_id}")
        assert del_res.status_code == 200
        assert del_res.json()["deleted"] is True

        assert len(app_client.get("/api/v1/documents").json()) == 0
        # Retrieval after deletion should return 0 hits safely
        q_res = app_client.post("/api/v1/retrieval", json={"query": "temporary", "top_k": 5})
        assert q_res.status_code == 200
        assert len(q_res.json()["hits"]) == 0


class TestRetrievalBoundariesAndFilters:
    def test_top_k_boundaries(self, app_client):
        # top_k=0 rejected by schema (ge=1)
        assert app_client.post("/api/v1/retrieval", json={"query": "test", "top_k": 0}).status_code == 422
        # top_k > max_top_k rejected
        assert app_client.post("/api/v1/retrieval", json={"query": "test", "top_k": 50}).status_code == 422
        # top_k within bounds accepted
        assert app_client.post("/api/v1/retrieval", json={"query": "test", "top_k": 10}).status_code == 200

    def test_document_id_filtering(self, app_client):
        d1 = app_client.post("/api/v1/documents/text", json={"title": "Doc1", "text": "apples and oranges"}).json()["id"]
        d2 = app_client.post("/api/v1/documents/text", json={"title": "Doc2", "text": "bananas and oranges"}).json()["id"]

        # Search without filter
        all_hits = app_client.post("/api/v1/retrieval", json={"query": "oranges", "top_k": 5}).json()["hits"]
        doc_ids = {h["chunk"]["document_id"] for h in all_hits}
        assert d1 in doc_ids and d2 in doc_ids

        # Search filtered to Doc1 only
        filtered_hits = app_client.post("/api/v1/retrieval", json={"query": "oranges", "top_k": 5, "document_ids": [d1]}).json()["hits"]
        assert all(h["chunk"]["document_id"] == d1 for h in filtered_hits)

        # Search with non-existent document ID -> 0 hits, no crash
        empty_hits = app_client.post("/api/v1/retrieval", json={"query": "oranges", "top_k": 5, "document_ids": ["does-not-exist"]}).json()["hits"]
        assert len(empty_hits) == 0

    def test_retrieval_modes(self, app_client):
        app_client.post("/api/v1/documents/text", json={"title": "Hybrid Test", "text": "Hybrid search blends sparse BM25 and dense retrieval."})
        for mode in ["sparse", "dense", "hybrid"]:
            res = app_client.post("/api/v1/retrieval", json={"query": "sparse BM25", "mode": mode, "top_k": 3})
            assert res.status_code == 200
            data = res.json()
            assert "hits" in data
            assert "diagnostics" in data

    def test_html_tag_stripping_and_sanitization(self, app_client):
        html_content = b"<html><head><script>alert('bad')</script><style>body{color:red}</style></head><body><h1>Main Title</h1><p>Clean paragraph text.</p></body></html>"
        res = app_client.post(
            "/api/v1/documents/upload",
            files={"file": ("page.html", io.BytesIO(html_content), "text/html")},
        )
        assert res.status_code == 200
        doc_id = res.json()["id"]
        doc = app_client.get(f"/api/v1/documents/{doc_id}").json()
        assert "alert" not in doc["text"]
        assert "color:red" not in doc["text"]
        assert "Clean paragraph text" in doc["text"]


class TestQueryAndGroundedAnswering:
    def test_safe_abstention_on_no_evidence(self, app_client):
        app_client.post("/api/v1/documents/text", json={"title": "Space", "text": "Planets orbit stars in elliptical paths."})
        res = app_client.post("/api/v1/query", json={"query": "cooking lasagna recipe"})
        assert res.status_code == 200
        data = res.json()
        assert data["abstained"] is True
        assert data["abstention_reason"] is not None
        assert "recipe" not in data["answer"].lower()

    def test_grounded_answer_and_citations(self, app_client):
        app_client.post("/api/v1/documents/text", json={"title": "Mars Rover", "text": "Perseverance landed on Mars in Jezero Crater in February 2021."})
        res = app_client.post("/api/v1/query", json={"query": "Where did Perseverance land?", "top_k": 2})
        assert res.status_code == 200
        data = res.json()
        assert data["abstained"] is False
        assert len(data["citations"]) >= 1
        citation = data["citations"][0]
        assert citation["label"].startswith("[C")
        assert citation["title"] == "Mars Rover"
        assert "Jezero Crater" in citation["excerpt"]
        assert citation["start_char"] is not None
        assert citation["end_char"] is not None

    def test_provider_required_for_transformations(self, app_client):
        assert app_client.post("/api/v1/query", json={"query": "q", "rewrite": True}).status_code == 422
        assert app_client.post("/api/v1/query", json={"query": "q", "hyde": True}).status_code == 422


class TestAuthSecurity:
    def test_auth_protection(self, auth_client):
        # Health & readiness are public
        assert auth_client.get("/api/v1/health").status_code == 200
        assert auth_client.get("/api/v1/ready").status_code == 200

        # Protected routes reject missing or bad keys
        assert auth_client.get("/api/v1/documents").status_code == 401
        assert auth_client.get("/api/v1/documents", headers={"X-API-Key": "wrong"}).status_code == 401

        # Protected routes accept correct key
        assert auth_client.get("/api/v1/documents", headers={"X-API-Key": "super-secret-key-123"}).status_code == 200
