# Frontend build prompt for RAGForge

Build the frontend for **RAGForge**, an evaluation-first Retrieval-Augmented Generation platform. Do not invent backend behavior: integrate with the existing FastAPI API described below and show limitations honestly.

## Product direction

RAGForge is not a generic document-chat screen. The interface should make retrieval quality, evidence, citations, abstention, and experiment comparisons first-class. Use a calm technical visual language: high information density, clear hierarchy, accessible contrast, restrained accent color, responsive layout, and excellent empty/loading/error states.

## Primary screens

1. **Workspace overview**
   - Indexed document count, chunk count if available, active retrieval mode, provider status, and latest evaluation run.
   - Explain whether the app is in offline extractive mode or provider-backed mode.
2. **Documents**
   - Upload `.txt`, `.md`, `.html`, and optional `.pdf` files.
   - Add plain text documents with title and metadata.
   - List, inspect, and delete documents; show chunk count and metadata.
   - Upload progress, unsupported-format errors, size-limit errors, and confirmation before delete.
3. **Ask / grounded query**
   - Query editor with retrieval mode (`sparse`, `dense`, `hybrid`), `top_k`, optional document filters, reranking, compression, rewrite, and HyDE controls.
   - Disable or clearly mark rewrite/HyDE unless the capabilities endpoint reports a configured provider.
   - Answer view must show `abstained`, abstention reason, diagnostics/limitations, exact `[C#]` citations, source title, document ID, chunk ID, excerpt, and character offsets.
   - Make it visually impossible to confuse a retrieval score with factual confidence. Label scores as retrieval signals.
   - If the backend abstains, make that a successful safe outcome, not an error.
4. **Retrieval inspector**
   - Show ranked hits and component scores separately: sparse, dense, RRF, rerank.
   - Explain that RRF is a fusion score and scores do not prove factuality.
   - Allow expanding exact chunk text and linking back to the source document.
5. **Evaluation / experiments**
   - Upload or select a local/custom dataset and configure mode, chunk size, overlap, top-k, and comparison grid.
   - Display Recall@K, MRR@K, and nDCG@K with evaluated/unavailable query counts.
   - Separate lexical proxies and evidence-overlap metrics from judge-dependent faithfulness, answer relevance, and citation correctness.
   - Show run ID, dataset SHA-256, config SHA-256, timestamp, baseline label, and reproducibility details.
   - Include result comparison by architecture, embedding mode, chunking strategy, and reranker when reports provide them.

## API integration

Base URL should be configurable via an environment variable. Use these endpoints:

- `GET /api/v1/health`
- `GET /api/v1/ready`
- `GET /api/v1/capabilities`
- `POST /api/v1/documents/text` with `{title,text,metadata}`
- `POST /api/v1/documents/upload` multipart form with `file` and optional `title`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/retrieval` with query and retrieval options
- `POST /api/v1/query` with query, retrieval options, and `rewrite`, `hyde`, `compress`

Send `X-API-Key` only when configured by the deployment. Never log or expose the key. Treat all API text as untrusted content: render source excerpts as text, not HTML, and avoid unsafe markdown/HTML injection.

## Interaction and accessibility requirements

- Keyboard navigable, semantic headings, labeled controls, visible focus, screen-reader-friendly status updates.
- Preserve query/options when navigating between answer and retrieval inspector.
- Use skeletons for loading and actionable error messages with retry where safe.
- Confirm destructive actions. Do not auto-submit a query while the user is typing.
- Responsive at mobile, tablet, and desktop widths; retrieval evidence remains readable on small screens.
- Do not use fabricated metrics, fake citations, or demo answers presented as real backend data.

## Suggested implementation boundary

Build only the frontend. Keep API client types, state management, visual components, and pages modular. Add a small mock adapter only for local UI development, clearly marked as mock and easy to remove. Do not change the backend contracts, do not add model downloads, and do not put secrets in frontend code.
