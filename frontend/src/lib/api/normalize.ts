import type {
  Chunk,
  Citation,
  DocumentDetail,
  DocumentSummary,
  Hit,
  QueryResult,
  RetrievalResult,
} from "./types";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Any = any;
const num = (v: unknown) => (typeof v === "number" && Number.isFinite(v) ? v : undefined);
const str = (v: unknown) => (typeof v === "string" ? v : v == null ? undefined : String(v));

export function normDoc(d: Any): DocumentDetail {
  return {
    document_id: str(d.document_id ?? d.id) ?? "",
    title: str(d.title) ?? "(untitled)",
    chunk_count: num(d.chunk_count ?? d.num_chunks ?? d.chunks?.length),
    metadata: d.metadata && typeof d.metadata === "object" ? d.metadata : undefined,
    created_at: str(d.created_at),
    char_count: num(d.char_count),
    text: str(d.text),
    chunks: Array.isArray(d.chunks) ? d.chunks.map(normChunk) : undefined,
  };
}

function normChunk(c: Any): Chunk {
  return {
    chunk_id: str(c.chunk_id ?? c.id) ?? "",
    text: str(c.text) ?? "",
    start_char: num(c.start_char ?? c.start),
    end_char: num(c.end_char ?? c.end),
  };
}

export function normDocList(r: unknown): DocumentSummary[] {
  const arr = Array.isArray(r) ? r : ((r as Any)?.documents ?? (r as Any)?.items ?? []);
  return (arr as Any[]).map(normDoc);
}

export function normHit(h: Any, i: number): Hit {
  const s = (h.scores ?? h.component_scores ?? {}) as Any;
  const c = (h.chunk ?? h) as Any;
  return {
    rank: num(h.rank) ?? i + 1,
    chunk_id: str(c.chunk_id ?? h.chunk_id ?? c.id) ?? "",
    document_id: str(c.document_id ?? h.document_id) ?? "",
    title: str(c.title ?? h.title ?? c.metadata?.title),
    text: str(c.text ?? h.text) ?? "",
    start_char: num(c.start_char ?? h.start_char),
    end_char: num(c.end_char ?? h.end_char),
    score: num(h.score),
    scores: {
      sparse: num(s.sparse ?? h.sparse_score),
      dense: num(s.dense ?? h.dense_score),
      rrf: num(s.rrf ?? h.rrf_score),
      rerank: num(s.rerank ?? h.rerank_score),
    },
  };
}

export function normRetrieval(r: Any, query: string): RetrievalResult {
  const hits = (r.hits ?? r.results ?? r.chunks ?? []) as Any[];
  return {
    query: str(r.query) ?? query,
    mode: str(r.mode),
    hits: hits.map(normHit),
    diagnostics: r.diagnostics,
  };
}

export function normQuery(r: Any): QueryResult {
  const cits = (r.citations ?? []) as Any[];
  const lim =
    r.limitations ??
    r.diagnostics?.limitations ??
    (r.diagnostics?.limitation ? [r.diagnostics.limitation] : []);
  return {
    answer: str(r.answer) ?? "",
    abstained: Boolean(r.abstained),
    abstention_reason: str(r.abstention_reason ?? r.reason) ?? null,
    citations: cits.map((c, i): Citation => {
      const raw = str(c.label ?? c.citation_id ?? c.marker) ?? `C${i + 1}`;
      return {
        label: raw.replace(/[[\]]/g, ""),
        chunk_id: str(c.chunk_id) ?? "",
        document_id: str(c.document_id) ?? "",
        title: str(c.title ?? c.source_title),
        excerpt: str(c.excerpt ?? c.text ?? c.quote) ?? "",
        start_char: num(c.start_char),
        end_char: num(c.end_char),
      };
    }),
    hits: ((r.hits ?? r.retrieved ?? r.contexts ?? []) as Any[]).map(normHit),
    diagnostics: r.diagnostics,
    limitations: Array.isArray(lim) ? lim.map(String) : [String(lim)],
    rewritten_query: str(r.rewritten_query) ?? null,
  };
}
