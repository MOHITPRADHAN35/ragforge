// Evaluation reports are produced offline by the RAGForge CLI; the API exposes
// no evaluation endpoint. Reports are loaded from local files and kept only in
// this browser's localStorage.
export type StoredReport = Record<string, unknown> & {
  _filename: string;
  _loaded_at: string;
  [key: string]: unknown;
};
const KEY = "ragforge.lastReport";

export function loadStoredReport(): StoredReport | null {
  try {
    const r = localStorage.getItem(KEY);
    return r ? JSON.parse(r) : null;
  } catch {
    return null;
  }
}
export function storeReport(r: StoredReport | null) {
  try {
    if (r) {
      localStorage.setItem(KEY, JSON.stringify(r));
    } else {
      localStorage.removeItem(KEY);
    }
  } catch {
    /* quota */
  }
}

export async function sha256(text: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export const RETRIEVAL_KEYS = /^(recall|mrr|ndcg|hit_rate|precision)(@|_at_|_)?\d*$/i;
export const PROXY_KEYS = /(lexical|overlap|evidence|rouge|token_f1|exact_match|bleu)/i;
export const JUDGE_KEYS = /(faithful|answer_relevance|citation_correct|groundedness|judge)/i;
