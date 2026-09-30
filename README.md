# RAGForge backend

RAGForge is an evaluation-first RAG backend. It starts offline and deterministic, while keeping model providers, rerankers, and an OpenAI-compatible generator opt-in.

## Project layout

```text
ragforge/
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── .env.example
│   ├── src/ragforge/
│   │   ├── api/          # FastAPI app and request/response schemas
│   │   ├── core/         # settings and provider adapters
│   │   ├── evaluation/   # BEIR/custom loaders, metrics, experiments, CLI
│   │   ├── generation/   # extractive and optional provider-backed answers
│   │   ├── ingestion/    # safe parsing and offset-preserving chunking
│   │   ├── retrieval/    # BM25, hash/dense, hybrid RRF, reranking
│   │   ├── storage/      # SQLite repository and schema migration
│   │   └── models.py     # shared dataclass contracts
│   └── tests/
├── frontend/             # TanStack Start / React UI
│   ├── src/
│   │   ├── routes/       # Workspace, Documents, Ask, Inspector, Evaluation
│   │   ├── components/   # RAG controls, cards, and UI components
│   │   └── lib/api/      # API client and normalizers
│   ├── package.json
│   └── vite.config.ts
├── datasets/sample_fixture.json
├── FRONTEND_PROMPT.md
└── README.md
```

## Run locally

### 1. Start the Backend

From the repository root or `backend`:

```powershell
pip install -e backend
python -m uvicorn ragforge.api.app:app --host 127.0.0.1 --port 8000 --reload
```

The API is available at `http://127.0.0.1:8000`; OpenAPI docs are at `http://127.0.0.1:8000/docs`.

Run backend tests:

```powershell
python -m pytest
```

### 2. Start the Frontend

From `frontend`:

```powershell
npm install
npm run dev
```

The frontend application opens at `http://127.0.0.1:5173/`. All API requests are automatically proxied to the backend at `http://127.0.0.1:8000`.


## Offline evaluation

From `ragforge`:

```powershell
$env:PYTHONPATH = "backend/src"
python -m ragforge.evaluation.cli datasets/sample_fixture.json `
  --output-dir evaluation-reports --mode sparse --chunk-size 400 800
```

Local BEIR directories are supported when they contain `corpus.jsonl`, `queries.jsonl`, and optionally `qrels/<split>.tsv`. Evaluation reports include dataset/config hashes, run IDs, retrieval metrics, and explicit unavailable values. Hash embeddings and lexical generation checks are labeled baselines—not semantic or factuality guarantees.

## Safety and limitations

- Ingestion accepts caller-provided bytes only; it does not fetch URLs or arbitrary server paths.
- Retrieved text is treated as untrusted context. Provider output must cite known `[C#]` labels, but citation validation is not formal factuality verification.
- Faithfulness, semantic answer relevance, and citation correctness remain unavailable unless an evaluation judge or gold labels are supplied.
- Query rewrite, HyDE, neural embeddings, reranking, PDF parsing, and provider generation are optional and never download models on startup.
