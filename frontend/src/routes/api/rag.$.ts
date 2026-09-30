import { createFileRoute } from "@tanstack/react-router";

// Server-side pass-through to the RAGForge FastAPI backend.
// RAGFORGE_API_URL (e.g. https://ragforge.example.com) and optional RAGFORGE_API_KEY
// are read on the server only, so the key never reaches the browser.
const ALLOWED =
  /^(health|ready|readiness|capabilities|config|documents(\/text|\/upload|\/[A-Za-z0-9._:-]+)?|retrieval|query)$/;

async function forward(request: Request, splat: string | undefined) {
  const base = process.env["RAGFORGE_API_URL"] || "http://127.0.0.1:8000";
  const path = (splat ?? "").replace(/^\/+/, "");
  if (!ALLOWED.test(path)) return Response.json({ detail: "Unknown endpoint" }, { status: 404 });

  const headers = new Headers();
  const ct = request.headers.get("content-type");
  if (ct) headers.set("content-type", ct);
  headers.set("accept", "application/json");
  const key = process.env["RAGFORGE_API_KEY"];
  if (key) headers.set("X-API-Key", key);

  const hasBody = !["GET", "HEAD", "DELETE"].includes(request.method);
  try {
    const url = new URL(request.url);
    const targetUrl = `${base.replace(/\/+$/, "")}/api/v1/${path}${url.search}`;
    const res = await fetch(targetUrl, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : null,
    });
    return new Response(res.body, {
      status: res.status,
      headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch {
    return Response.json({ detail: "Could not reach the RAGForge API." }, { status: 502 });
  }
}

export const Route = createFileRoute("/api/rag/$")({
  server: {
    handlers: {
      GET: ({ request, params }) => forward(request, params._splat),
      POST: ({ request, params }) => forward(request, params._splat),
      DELETE: ({ request, params }) => forward(request, params._splat),
    },
  },
});
