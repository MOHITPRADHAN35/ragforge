import { mock } from "./mock";
import { normDoc, normDocList, normQuery, normRetrieval } from "./normalize";
import {
  ApiError,
  type Capabilities,
  type DocumentDetail,
  type DocumentSummary,
  type QueryOptions,
  type QueryResult,
  type RetrievalOptions,
  type RetrievalResult,
} from "./types";

// All real calls go through the same-origin /api/rag proxy, which injects the
// backend base URL and API key server-side.
const BASE = "/api/rag";
const MOCK_KEY = "ragforge.mock";

export function isMockMode(): boolean {
  if (typeof window === "undefined") return false;
  return (
    import.meta.env["VITE_RAGFORGE_MOCK"] === "true" ||
    window.localStorage.getItem(MOCK_KEY) === "1"
  );
}
export function setMockMode(on: boolean) {
  if (on) localStorage.setItem(MOCK_KEY, "1");
  else localStorage.removeItem(MOCK_KEY);
  window.location.reload();
}

async function detailOf(res: Response): Promise<string> {
  try {
    const j = await res.json();
    const d = j?.detail ?? j?.message ?? j?.error;
    if (typeof d === "string") return d;
    if (Array.isArray(d))
      return d
        .map((x: unknown) =>
          typeof x === "object" && x && "msg" in x
            ? String((x as { msg: unknown }).msg)
            : JSON.stringify(x),
        )
        .join("; ");
    return `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}/${path}`, init);
  } catch {
    throw new ApiError("Network error — could not reach the server.", 0, true);
  }
  if (!res.ok)
    throw new ApiError(await detailOf(res), res.status, res.status >= 500 || res.status === 429);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
});

function retrievalBody(o: RetrievalOptions) {
  return {
    query: o.query,
    mode: o.mode,
    top_k: o.top_k,
    rerank: o.rerank,
    ...(o.document_ids?.length ? { document_ids: o.document_ids } : {}),
  };
}

export const api = {
  health: () => (isMockMode() ? mock.health() : req<Record<string, unknown>>("health")),
  ready: () => (isMockMode() ? mock.ready() : req<Record<string, unknown>>("ready")),
  capabilities: (): Promise<Capabilities> =>
    isMockMode() ? mock.capabilities() : req("capabilities"),
  listDocuments: async (): Promise<DocumentSummary[]> =>
    isMockMode() ? mock.listDocuments() : normDocList(await req("documents")),
  getDocument: async (id: string): Promise<DocumentDetail> =>
    isMockMode() ? mock.getDocument(id) : normDoc(await req(`documents/${encodeURIComponent(id)}`)),
  deleteDocument: (id: string) =>
    isMockMode()
      ? mock.deleteDocument(id)
      : req(`documents/${encodeURIComponent(id)}`, { method: "DELETE" }),
  addText: async (title: string, text: string, metadata: Record<string, unknown>) =>
    isMockMode()
      ? mock.addText(title, text, metadata)
      : normDoc(await req("documents/text", json({ title, text, metadata }))),
  retrieval: async (o: RetrievalOptions): Promise<RetrievalResult> =>
    isMockMode()
      ? mock.retrieval(o)
      : normRetrieval(await req("retrieval", json(retrievalBody(o))), o.query),
  query: async (o: QueryOptions): Promise<QueryResult> =>
    isMockMode()
      ? mock.query(o)
      : normQuery(
          await req(
            "query",
            json({ ...retrievalBody(o), rewrite: o.rewrite, hyde: o.hyde, compress: o.compress }),
          ),
        ),

  upload(
    file: File,
    title: string | undefined,
    onProgress: (pct: number) => void,
  ): Promise<DocumentSummary> {
    if (isMockMode()) {
      return file.text().then((t) => {
        onProgress(100);
        return mock.addText(title || file.name, t, { filename: file.name });
      });
    }
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const fd = new FormData();
      fd.append("file", file);
      if (title) fd.append("title", title);
      const url = title
        ? `${BASE}/documents/upload?title=${encodeURIComponent(title)}`
        : `${BASE}/documents/upload`;
      xhr.open("POST", url);
      xhr.upload.onprogress = (e) =>
        e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
      xhr.onerror = () => reject(new ApiError("Network error during upload.", 0, true));
      xhr.onload = () => {
        let body: Record<string, unknown> | null = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* ignore */
        }
        if (xhr.status >= 200 && xhr.status < 300) return resolve(normDoc(body ?? {}));
        const msg =
          typeof body?.detail === "string"
            ? body.detail
            : xhr.status === 413
              ? "File exceeds the server's size limit."
              : xhr.status === 415
                ? "Unsupported file format."
                : `Upload failed (${xhr.status})`;
        reject(new ApiError(msg, xhr.status, xhr.status >= 500));
      };
      xhr.send(fd);
    });
  },
};
