from __future__ import annotations

import uuid
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from ragforge.core.retrieval import retrieve
from ragforge.core.settings import Settings
from ragforge.generation import GroundedGenerator
from ragforge.generation.grounded import ProviderError
from ragforge.models import Document, RetrievalOptions
from ragforge.storage import SQLiteStore
from .schemas import QueryIn, RetrievalIn, TextDocumentIn, answer_view, document_view, hit_view


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    store = SQLiteStore(settings.database_path)
    api = FastAPI(title="Ragforge", version="0.1.0")
    api.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def auth(x_api_key: Annotated[str | None, Header()] = None):
        if settings.api_key and x_api_key != settings.api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    def bounded_options(body: RetrievalIn) -> RetrievalOptions:
        config = getattr(body, "retrieval", None) or body
        if config.top_k > settings.max_top_k:
            raise HTTPException(422, f"top_k must be <= {settings.max_top_k}")
        return RetrievalOptions(mode=config.mode, top_k=config.top_k, candidate_k=config.candidate_k, rrf_k=config.rrf_k, rerank=config.rerank, document_ids=config.document_ids)

    def ingest(title: str, text: str, metadata: dict) -> dict:
        if len(text) > settings.max_input_chars:
            raise HTTPException(413, "Input exceeds max_input_chars")
        try:
            from ragforge.ingestion import parse_bytes, chunk_document
            # parse_bytes is for uploaded bytes; text is already decoded and must not be treated as a path.
            document = Document(str(uuid.uuid4()), title, text, {**metadata, "title": title})
            chunks = chunk_document(document)
        except ImportError:
            # Useful only while the independent ingestion component is not installed.
            from ragforge.models import Chunk
            document = Document(str(uuid.uuid4()), title, text, {**metadata, "title": title})
            chunks = [Chunk(str(uuid.uuid4()), document.id, text, 0, 0, len(text), {"title": title})]
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        store.put_document(document, chunks)
        return document_view(document) | {"chunk_count": len(chunks)}

    @api.get("/health")
    @api.get("/api/v1/health")
    def health():
        return {"status": "ok", "service": "ragforge"}

    @api.get("/ready")
    @api.get("/readiness")
    @api.get("/api/v1/ready")
    @api.get("/api/v1/readiness")
    def ready():
        try:
            store.list_documents()
            return {"status": "ready", "schema_version": 1}
        except Exception as exc:
            raise HTTPException(503, "storage unavailable") from exc

    @api.get("/api/v1/capabilities")
    @api.get("/api/v1/config")
    def capabilities():
        return settings.public()

    @api.post("/api/v1/documents/text", dependencies=[Depends(auth)])
    def add_text(body: TextDocumentIn):
        return ingest(body.title, body.text, body.metadata)

    @api.post("/api/v1/documents/upload", dependencies=[Depends(auth)])
    def add_upload(file: UploadFile = File(...), title: str | None = Query(default=None, max_length=300)):
        # Read one bounded extra byte so oversized input is rejected without unbounded memory growth.
        raw = file.file.read(settings.max_upload_bytes + 1)
        if len(raw) > settings.max_upload_bytes:
            raise HTTPException(413, "Upload exceeds max_upload_bytes")
        file_name = Path(file.filename or "upload.txt").name
        doc_title = title or file_name
        if not doc_title:
            doc_title = "upload"
        fmt_name = file_name if Path(file_name).suffix else doc_title
        try:
            from ragforge.ingestion import parse_bytes
            text = parse_bytes(fmt_name, raw)
        except ValueError as exc:
            raise HTTPException(415, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(501, str(exc)) from exc
        except ImportError:
            text = raw.decode("utf-8", errors="replace")
        return ingest(doc_title, text, {"filename": file_name, "content_type": file.content_type})

    @api.get("/api/v1/documents", dependencies=[Depends(auth)])
    def list_documents():
        docs = store.list_documents()
        chunks = store.get_chunks()
        counts: dict[str, int] = {}
        for c in chunks:
            counts[c.document_id] = counts.get(c.document_id, 0) + 1
        return [document_view(d) | {"chunk_count": counts.get(d.id, 0), "char_count": len(d.text)} for d in docs]

    @api.get("/api/v1/documents/{document_id}", dependencies=[Depends(auth)])
    def get_document(document_id: str):
        d = store.get_document(document_id)
        if not d:
            raise HTTPException(404, "Document not found")
        chunks = store.get_chunks([d.id])
        return document_view(d) | {
            "chunk_count": len(chunks),
            "char_count": len(d.text),
            "chunks": [hit_view(type("H", (), {"chunk": c, "score": 0, "scores": {}})()) for c in chunks],
        }


    @api.delete("/api/v1/documents/{document_id}", dependencies=[Depends(auth)])
    def delete_document(document_id: str):
        if not store.delete_document(document_id):
            raise HTTPException(404, "Document not found")
        return {"deleted": True, "id": document_id}

    @api.post("/api/v1/retrieval", dependencies=[Depends(auth)])
    def retrieval(body: RetrievalIn):
        options = bounded_options(body)
        hits = retrieve(store.get_chunks(options.document_ids), body.query, options, embedder_spec=settings.embedder, reranker_spec=settings.reranker)
        return {"query": body.query, "hits": [hit_view(h) for h in hits], "diagnostics": {"mode": "retrieval", "limitation": "Scores are retrieval signals, not factuality verification."}}

    @api.post("/api/v1/query", dependencies=[Depends(auth)])
    def query(body: QueryIn):
        if (body.rewrite or body.hyde) and not settings.provider_enabled:
            raise HTTPException(422, "rewrite/hyde require a configured provider")
        options = bounded_options(body)
        generator = GroundedGenerator(settings)
        try:
            retrieval_query = generator.transform_query(body.query, rewrite=body.rewrite, hyde=body.hyde)
        except ProviderError as exc:
            raise HTTPException(502, str(exc)) from exc
        hits = retrieve(store.get_chunks(options.document_ids), retrieval_query, options, embedder_spec=settings.embedder, reranker_spec=settings.reranker)
        answer = generator.answer(body.query, hits, compress=body.compress)
        if body.rewrite:
            answer.diagnostics["rewrite"] = "requested; provider mode"
        if body.hyde:
            answer.diagnostics["hyde"] = "requested; provider mode"
        return answer_view(answer)

    return api


app = create_app()
