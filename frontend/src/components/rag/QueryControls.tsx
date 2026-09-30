import { useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { setOptions, useQueryState } from "@/lib/query-store";
import type { RetrievalMode } from "@/lib/api/types";
import { documentsQuery, useCapabilities } from "./common";

export function QueryControls({
  onSubmit,
  busy,
  submitLabel,
  generation,
}: {
  onSubmit: () => void;
  busy: boolean;
  submitLabel: string;
  generation?: boolean;
}) {
  const { options: o } = useQueryState();
  const caps = useCapabilities();
  const docs = useQuery(documentsQuery);
  const provider = caps.data?.provider_configured === true;
  const modes = (caps.data?.retrieval_modes as RetrievalMode[] | undefined) ?? [
    "sparse",
    "dense",
    "hybrid",
  ];

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (o.query.trim()) onSubmit();
  };

  const toggle = (
    id: string,
    key: "rerank" | "compress" | "rewrite" | "hyde",
    label: string,
    hint: string,
    disabled = false,
  ) => (
    <div className="flex items-start justify-between gap-3">
      <div>
        <Label htmlFor={id} className={disabled ? "text-muted-foreground" : ""}>
          {label}
        </Label>
        <p id={`${id}-h`} className="text-xs text-muted-foreground">
          {hint}
        </p>
      </div>
      <Switch
        id={id}
        aria-describedby={`${id}-h`}
        checked={o[key] && !disabled}
        disabled={disabled}
        onCheckedChange={(v) => setOptions({ [key]: v })}
      />
    </div>
  );

  return (
    <form onSubmit={submit} className="space-y-4" aria-label="Query">
      <div>
        <Label htmlFor="q">Query</Label>
        <Textarea
          id="q"
          rows={3}
          className="mt-1.5 font-mono text-sm"
          placeholder="Ask a question grounded in your indexed documents…"
          value={o.query}
          onChange={(e) => setOptions({ query: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(e);
          }}
        />
        <p className="mt-1 text-xs text-muted-foreground">
          Submit with the button or Ctrl/⌘ + Enter.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="mode">Retrieval mode</Label>
          <select
            id="mode"
            value={o.mode}
            onChange={(e) => setOptions({ mode: e.target.value as RetrievalMode })}
            className="mt-1.5 h-9 w-full rounded-md border bg-background px-2 font-mono text-sm"
          >
            {modes.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="topk">top_k</Label>
          <input
            id="topk"
            type="number"
            min={1}
            max={50}
            value={o.top_k}
            onChange={(e) =>
              setOptions({ top_k: Math.max(1, Math.min(50, Number(e.target.value) || 1)) })
            }
            className="mt-1.5 h-9 w-full rounded-md border bg-background px-2 font-mono text-sm"
          />
        </div>
      </div>
      <fieldset>
        <legend className="text-sm font-medium">
          Document filter <span className="font-normal text-muted-foreground">(optional)</span>
        </legend>
        <div className="mt-1.5 max-h-32 space-y-1 overflow-y-auto rounded-md border p-2">
          {docs.isLoading && <p className="text-xs text-muted-foreground">Loading documents…</p>}
          {docs.isError && <p className="text-xs text-destructive">Couldn't load documents.</p>}
          {docs.data?.length === 0 && (
            <p className="text-xs text-muted-foreground">No documents indexed.</p>
          )}
          {docs.data?.map((d) => (
            <label key={d.document_id} className="flex items-center gap-2 text-xs">
              <input
                type="checkbox"
                checked={o.document_ids?.includes(d.document_id) ?? false}
                onChange={(e) =>
                  setOptions({
                    document_ids: e.target.checked
                      ? [...(o.document_ids ?? []), d.document_id]
                      : (o.document_ids ?? []).filter((x) => x !== d.document_id),
                  })
                }
              />
              <span className="truncate">{d.title}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <div className="space-y-3 border-t pt-3">
        {toggle(
          "rerank",
          "rerank",
          "Rerank",
          caps.data?.reranker_available === false
            ? "Reranker not reported available."
            : "Re-score retrieved chunks.",
          caps.data?.reranker_available === false,
        )}
        {generation && (
          <>
            {toggle("compress", "compress", "Compress context", "Trim evidence before answering.")}
            {toggle(
              "rewrite",
              "rewrite",
              "Query rewrite",
              provider
                ? "Uses the configured provider."
                : "Requires a configured provider — unavailable.",
              !provider,
            )}
            {toggle(
              "hyde",
              "hyde",
              "HyDE",
              provider
                ? "Hypothetical document expansion."
                : "Requires a configured provider — unavailable.",
              !provider,
            )}
          </>
        )}
      </div>
      <Button type="submit" className="w-full" disabled={busy || !o.query.trim()}>
        {busy ? "Running…" : submitLabel}
      </Button>
    </form>
  );
}
