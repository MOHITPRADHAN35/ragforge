import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, RotateCw } from "lucide-react";
import type { ReactNode } from "react";
import { api } from "@/lib/api/client";
import { ApiError, type ComponentScores } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const capabilitiesQuery = {
  queryKey: ["capabilities"],
  queryFn: api.capabilities,
  retry: 1,
  staleTime: 60_000,
};
export const documentsQuery = { queryKey: ["documents"], queryFn: api.listDocuments, retry: 1 };
export const useCapabilities = () => useQuery(capabilitiesQuery);

export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3 border-b pb-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      {actions}
    </div>
  );
}

export function Panel({
  title,
  children,
  className,
  aside,
}: {
  title?: ReactNode;
  children: ReactNode;
  className?: string;
  aside?: ReactNode;
}) {
  return (
    <section className={cn("rounded-md border bg-card", className)}>
      {title && (
        <div className="flex items-center justify-between gap-2 border-b px-4 py-2.5">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            {title}
          </h2>
          {aside}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : "Something went wrong.";
  const retryable = !(error instanceof ApiError) || error.retryable;
  return (
    <div
      role="alert"
      className="flex flex-wrap items-start gap-3 rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm"
    >
      <AlertTriangle className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden />
      <div className="flex-1">
        <p className="font-medium text-destructive">{msg}</p>
        {error instanceof ApiError && error.status === 503 && (
          <p className="mt-1 text-muted-foreground">
            Set RAGFORGE_API_URL on the deployment, or enable mock mode from the sidebar for UI
            development.
          </p>
        )}
      </div>
      {onRetry && retryable && (
        <Button size="sm" variant="outline" onClick={onRetry}>
          <RotateCw className="size-3.5" /> Retry
        </Button>
      )}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="rounded-md border border-dashed p-8 text-center">
      <p className="text-sm font-medium">{title}</p>
      {children && <div className="mt-1 text-sm text-muted-foreground">{children}</div>}
    </div>
  );
}

export function Mono({ children, className }: { children: ReactNode; className?: string }) {
  return <code className={cn("break-all font-mono text-[0.78rem]", className)}>{children}</code>;
}

export function Tag({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "primary" | "success" | "warning" | "destructive";
}) {
  const tones = {
    muted: "bg-muted text-muted-foreground border-border",
    primary: "bg-accent text-accent-foreground border-primary/30",
    success: "bg-success/10 text-success border-success/30",
    warning: "bg-warning/10 text-warning border-warning/40",
    destructive: "bg-destructive/10 text-destructive border-destructive/30",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-mono text-[0.7rem] font-medium",
        tones[tone],
      )}
    >
      {children}
    </span>
  );
}

export const fmt = (v: number | null | undefined, d = 4) =>
  v == null ? "—" : Number.isInteger(v) ? String(v) : v.toFixed(d);

/** Retrieval signals — deliberately styled as raw numbers, never as percentages or confidence. */
export function ScoreGrid({ scores, compact }: { scores: ComponentScores; compact?: boolean }) {
  const items: [string, number | null | undefined, string][] = [
    ["sparse", scores.sparse, "BM25-style lexical match score"],
    ["dense", scores.dense, "Embedding similarity"],
    ["rrf", scores.rrf, "Reciprocal Rank Fusion — a rank-fusion score, not a probability"],
    ["rerank", scores.rerank, "Reranker relevance score"],
  ];
  return (
    <dl
      className={cn(
        "grid grid-cols-4 gap-px overflow-hidden rounded border bg-border",
        compact && "text-[0.7rem]",
      )}
      aria-label="Retrieval signals (not factual confidence)"
    >
      {items.map(([k, v, t]) => (
        <div key={k} className="bg-card px-2 py-1" title={t}>
          <dt className="font-mono text-[0.65rem] uppercase text-muted-foreground">{k}</dt>
          <dd className={cn("font-mono text-xs", v == null && "text-muted-foreground")}>
            {fmt(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}

export function SignalNote() {
  return (
    <p className="text-xs text-muted-foreground">
      <span className="font-medium text-foreground">Retrieval signals only.</span> Scores rank how
      well a chunk matches the query. They are not factual confidence and do not prove an answer is
      correct. RRF is a rank-fusion value.
    </p>
  );
}

export function KV({ data }: { data: Record<string, unknown> | undefined }) {
  if (!data || !Object.keys(data).length)
    return <p className="text-sm text-muted-foreground">None reported.</p>;
  return (
    <dl className="grid grid-cols-[minmax(7rem,auto)_1fr] gap-x-3 gap-y-1 text-sm">
      {Object.entries(data).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-mono text-xs text-muted-foreground">{k}</dt>
          <dd className="font-mono text-xs break-all">
            {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
