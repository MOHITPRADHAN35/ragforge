// ============================================================================
// MOCK ADAPTER — for local UI development only. Every response is fabricated
// and the UI shows a persistent "Mock data" banner while it is active.
// Remove this file and the `isMockMode` branch in client.ts to drop it.
// ============================================================================
import type {
  Capabilities,
  DocumentDetail,
  QueryOptions,
  QueryResult,
  RetrievalOptions,
  RetrievalResult,
  Hit,
} from "./types";

const docs: DocumentDetail[] = [
  {
    document_id: "mock-doc-1",
    title: "[MOCK] Chunking notes",
    metadata: { source: "mock" },
    text: "Chunk size controls how much text each retrieval unit holds. Overlap preserves context across chunk boundaries. Smaller chunks raise precision but can drop context.",
  },
];

function chunk(d: DocumentDetail) {
  const text = d.text ?? "";
  const parts = text.split(/(?<=\.)\s+/);
  let pos = 0;
  return parts.map((p, i) => {
    const start = text.indexOf(p, pos);
    pos = start + p.length;
    return {
      chunk_id: `${d.document_id}:c${i}`,
      text: p,
      start_char: start,
      end_char: start + p.length,
    };
  });
}

const wait = (ms = 350) => new Promise((r) => setTimeout(r, ms));
const tokens = (s: string) => s.toLowerCase().match(/[a-z0-9]+/g) ?? [];

export const mock = {
  async health() {
    await wait(100);
    return { status: "ok (mock)" };
  },
  async ready() {
    await wait(100);
    return { status: "ready (mock)" };
  },
  async capabilities(): Promise<Capabilities> {
    await wait(100);
    return {
      provider_configured: false,
      provider: null,
      generation_mode: "extractive",
      retrieval_modes: ["sparse", "dense", "hybrid"],
      reranker_available: true,
      dense_available: true,
      pdf_supported: false,
      max_upload_bytes: 5_000_000,
      mock: true,
    };
  },
  async listDocuments() {
    await wait();
    return docs.map((d) => ({ ...d, chunk_count: chunk(d).length, text: undefined }));
  },
  async getDocument(id: string) {
    await wait();
    const d = docs.find((x) => x.document_id === id);
    if (!d) throw Object.assign(new Error("Document not found"), { status: 404 });
    return { ...d, chunks: chunk(d), chunk_count: chunk(d).length };
  },
  async addText(title: string, text: string, metadata: Record<string, unknown>) {
    await wait();
    const d = { document_id: `mock-doc-${Date.now()}`, title: `[MOCK] ${title}`, text, metadata };
    docs.push(d);
    return { ...d, chunk_count: chunk(d).length };
  },
  async deleteDocument(id: string) {
    await wait();
    const i = docs.findIndex((d) => d.document_id === id);
    if (i >= 0) docs.splice(i, 1);
    return { deleted: true };
  },
  async retrieval(o: RetrievalOptions): Promise<RetrievalResult> {
    await wait();
    const q = new Set(tokens(o.query));
    const hits: Hit[] = docs
      .filter((d) => !o.document_ids?.length || o.document_ids.includes(d.document_id))
      .flatMap((d) =>
        chunk(d).map((c) => ({ d, c, s: tokens(c.text).filter((t) => q.has(t)).length })),
      )
      .filter((x) => x.s > 0)
      .sort((a, b) => b.s - a.s)
      .slice(0, o.top_k)
      .map((x, i) => ({
        rank: i + 1,
        chunk_id: x.c.chunk_id,
        document_id: x.d.document_id,
        title: x.d.title,
        text: x.c.text,
        start_char: x.c.start_char,
        end_char: x.c.end_char,
        score: x.s,
        scores: {
          sparse: o.mode !== "dense" ? x.s : null,
          dense: o.mode !== "sparse" ? x.s / 10 : null,
          rrf: o.mode === "hybrid" ? 1 / (60 + i + 1) : null,
          rerank: o.rerank ? x.s / 5 : null,
        },
      }));
    return { query: o.query, mode: o.mode, hits, diagnostics: { adapter: "mock" } };
  },
  async query(o: QueryOptions): Promise<QueryResult> {
    const r = await mock.retrieval(o);
    if (!r.hits.length) {
      return {
        answer: "",
        abstained: true,
        abstention_reason: "No retrieved evidence overlaps the query (mock).",
        citations: [],
        hits: [],
        limitations: ["Mock adapter: extractive keyword overlap only."],
        diagnostics: { adapter: "mock" },
      };
    }
    const top = r.hits.slice(0, 2);
    return {
      answer: top.map((h, i) => `${h.text} [C${i + 1}]`).join(" "),
      abstained: false,
      citations: top.map((h, i) => ({
        label: `C${i + 1}`,
        chunk_id: h.chunk_id,
        document_id: h.document_id,
        title: h.title,
        excerpt: h.text,
        start_char: h.start_char,
        end_char: h.end_char,
      })),
      hits: r.hits,
      limitations: ["Mock adapter: fabricated for UI development, not backend output."],
      diagnostics: { adapter: "mock", mode: o.mode },
    };
  },
};
