import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Fragment } from "react";
import { ShieldCheck } from "lucide-react";
import { api } from "@/lib/api/client";
import { setQueryState, useQueryState } from "@/lib/query-store";
import type { QueryResult } from "@/lib/api/types";
import { Skeleton } from "@/components/ui/skeleton";
import { QueryControls } from "@/components/rag/QueryControls";
import { Empty, ErrorState, KV, Mono, PageHeader, Panel, Tag } from "@/components/rag/common";

export const Route = createFileRoute("/ask")({
  head: () => ({
    meta: [
      { title: "Ask — grounded query — RAGForge" },
      {
        name: "description",
        content:
          "Ask questions answered only from retrieved evidence, with exact citations and safe abstention.",
      },
      { property: "og:title", content: "Ask — grounded query — RAGForge" },
      {
        property: "og:description",
        content:
          "Ask questions answered only from retrieved evidence, with exact citations and safe abstention.",
      },
    ],
  }),
  component: AskPage,
});

function AskPage() {
  const { options, answer } = useQueryState();
  const m = useMutation({
    mutationFn: api.query,
    onSuccess: (r) =>
      setQueryState({
        answer: r,
        retrieval: r.hits.length
          ? { query: options.query, mode: options.mode, hits: r.hits, diagnostics: r.diagnostics }
          : null,
      }),
  });

  return (
    <>
      <PageHeader
        title="Ask"
        description="Answers are built only from retrieved chunks. Every claim should carry a [C#] citation; if evidence is insufficient, the system abstains."
      />
      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Panel title="Query & options" className="self-start lg:sticky lg:top-6">
          <QueryControls
            generation
            busy={m.isPending}
            submitLabel="Ask"
            onSubmit={() => m.mutate(options)}
          />
        </Panel>
        <div className="space-y-4" aria-live="polite" aria-busy={m.isPending}>
          {m.isPending && (
            <div className="space-y-3">
              <Skeleton className="h-32" />
              <Skeleton className="h-24" />
            </div>
          )}
          {m.isError && <ErrorState error={m.error} onRetry={() => m.mutate(options)} />}
          {!m.isPending && !answer && !m.isError && (
            <Empty title="No query yet">
              Write a question and press Ask. Nothing is sent while you type.
            </Empty>
          )}
          {!m.isPending && answer && <AnswerView r={answer} />}
        </div>
      </div>
    </>
  );
}

function renderWithCitations(text: string, labels: Set<string>) {
  return text.split(/(\[C\d+\])/g).map((part, i) => {
    const m = part.match(/^\[(C\d+)\]$/);
    if (!m) return <Fragment key={i}>{part}</Fragment>;
    const ok = labels.has(m[1] ?? "");
    return ok ? (
      <a
        key={i}
        href={`#cit-${m[1]}`}
        className="mx-0.5 rounded bg-accent px-1 font-mono text-xs font-semibold text-accent-foreground hover:underline"
      >
        {part}
      </a>
    ) : (
      <span
        key={i}
        className="mx-0.5 rounded bg-destructive/10 px-1 font-mono text-xs text-destructive"
        title="Citation not present in citation list"
      >
        {part}
      </span>
    );
  });
}

function AnswerView({ r }: { r: QueryResult }) {
  const labels = new Set(r.citations.map((c) => c.label));
  return (
    <>
      {r.abstained ? (
        <section
          className="rounded-md border border-success/40 bg-success/5 p-4"
          aria-labelledby="abst"
        >
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-5 text-success" aria-hidden />
            <h2 id="abst" className="font-semibold text-success">
              Abstained — safe outcome
            </h2>
          </div>
          <p className="mt-2 text-sm">
            The system declined to answer because the retrieved evidence was not sufficient to
            support one. This is intended behavior, not an error.
          </p>
          {r.abstention_reason && (
            <p className="mt-2 text-sm">
              <span className="font-medium">Reason:</span> {r.abstention_reason}
            </p>
          )}
        </section>
      ) : (
        <Panel title="Answer" aside={<Tag tone="primary">abstained: false</Tag>}>
          {r.rewritten_query && (
            <p className="mb-2 text-xs text-muted-foreground">
              Rewritten query: <Mono>{r.rewritten_query}</Mono>
            </p>
          )}
          <p className="whitespace-pre-wrap leading-relaxed">
            {renderWithCitations(r.answer, labels)}
          </p>
        </Panel>
      )}

      <Panel title={`Citations (${r.citations.length})`}>
        {r.citations.length === 0 ? (
          <p className="text-sm text-muted-foreground">No citations returned.</p>
        ) : (
          <ol className="space-y-3">
            {r.citations.map((c) => (
              <li
                key={c.label}
                id={`cit-${c.label}`}
                className="scroll-mt-6 rounded border p-3 target:ring-2 target:ring-ring"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Tag tone="primary">[{c.label}]</Tag>
                  <span className="text-sm font-medium">{c.title ?? "(untitled source)"}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">
                  doc <Mono>{c.document_id}</Mono> · chunk <Mono>{c.chunk_id}</Mono>
                  {c.start_char != null && (
                    <>
                      {" "}
                      · chars{" "}
                      <Mono>
                        {c.start_char}–{c.end_char}
                      </Mono>
                    </>
                  )}
                </p>
                <blockquote className="mt-2 border-l-2 border-primary/50 pl-3 text-sm whitespace-pre-wrap">
                  {c.excerpt}
                </blockquote>
                {c.document_id && (
                  <Link
                    to="/documents"
                    search={{ id: c.document_id }}
                    className="mt-2 inline-block text-xs font-medium text-primary hover:underline"
                  >
                    Open source document →
                  </Link>
                )}
              </li>
            ))}
          </ol>
        )}
      </Panel>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel title="Limitations">
          {r.limitations.length ? (
            <ul className="list-disc space-y-1 pl-4 text-sm">
              {r.limitations.map((l, i) => (
                <li key={i}>{l}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">None reported.</p>
          )}
        </Panel>
        <Panel title="Diagnostics">
          <KV data={r.diagnostics} />
        </Panel>
      </div>
      {r.hits.length > 0 && (
        <p className="text-sm">
          <Link to="/inspector" className="font-medium text-primary hover:underline">
            Inspect the {r.hits.length} retrieved chunks and their retrieval signals →
          </Link>
        </p>
      )}
    </>
  );
}
