// Types mirror the RAGForge FastAPI responses. Fields are optional where the
// backend may omit them; normalizers in normalize.ts tolerate variants.
export type RetrievalMode = "sparse" | "dense" | "hybrid";

export interface Capabilities {
  provider_configured?: boolean | undefined;
  provider?: string | null | undefined;
  generation_mode?: string | undefined;
  retrieval_modes?: string[] | undefined;
  default_retrieval_mode?: string | undefined;
  reranker_available?: boolean | undefined;
  dense_available?: boolean | undefined;
  pdf_supported?: boolean | undefined;
  max_upload_bytes?: number | undefined;
  supported_extensions?: string[] | undefined;
  [k: string]: unknown;
}

export interface DocumentSummary {
  document_id: string;
  title: string;
  chunk_count?: number | undefined;
  metadata?: Record<string, unknown> | undefined;
  created_at?: string | undefined;
  char_count?: number | undefined;
}

export interface Chunk {
  chunk_id: string;
  text: string;
  start_char?: number | undefined;
  end_char?: number | undefined;
}

export interface DocumentDetail extends DocumentSummary {
  text?: string | undefined;
  chunks?: Chunk[] | undefined;
}

export interface ComponentScores {
  sparse?: number | null | undefined;
  dense?: number | null | undefined;
  rrf?: number | null | undefined;
  rerank?: number | null | undefined;
}

export interface Hit {
  rank: number;
  chunk_id: string;
  document_id: string;
  title?: string | undefined;
  text: string;
  start_char?: number | undefined;
  end_char?: number | undefined;
  score?: number | null | undefined;
  scores: ComponentScores;
}

export interface Citation {
  label: string; // e.g. "C1"
  chunk_id: string;
  document_id: string;
  title?: string | undefined;
  excerpt: string;
  start_char?: number | undefined;
  end_char?: number | undefined;
}

export interface RetrievalOptions {
  query: string;
  mode: RetrievalMode;
  top_k: number;
  document_ids?: string[] | undefined;
  rerank: boolean;
}

export interface QueryOptions extends RetrievalOptions {
  rewrite: boolean;
  hyde: boolean;
  compress: boolean;
}

export interface RetrievalResult {
  query: string;
  mode?: string | undefined;
  hits: Hit[];
  diagnostics?: Record<string, unknown> | undefined;
}

export interface QueryResult {
  answer: string;
  abstained: boolean;
  abstention_reason?: string | null | undefined;
  citations: Citation[];
  hits: Hit[];
  diagnostics?: Record<string, unknown> | undefined;
  limitations: string[];
  rewritten_query?: string | null | undefined;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public retryable: boolean,
  ) {
    super(message);
  }
}
