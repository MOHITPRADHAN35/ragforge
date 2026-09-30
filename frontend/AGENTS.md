<!-- LOVABLE:BEGIN -->

> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.

<!-- LOVABLE:END -->

- RAGForge API calls go through the same-origin proxy `/api/rag/*` (server env RAGFORGE_API_URL, RAGFORGE_API_KEY) — keeps the API key off the client.
- `src/lib/api/mock.ts` is a removable dev-only adapter toggled via localStorage `ragforge.mock` or VITE_RAGFORGE_MOCK — never present its output as real.
- Evaluation reports are loaded from local JSON files; the backend exposes no eval endpoint, so the UI must not fabricate runs.
