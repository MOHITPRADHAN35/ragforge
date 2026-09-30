import { createFileRoute, Link } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { setQueryState, useQueryState } from "@/lib/query-store";
import { Skeleton } from "@/components/ui/skeleton";
import { QueryControls } from "@/components/rag/QueryControls";
import { HitCard } from "@/components/rag/HitCard";
import {
  Empty,
  ErrorState,
  KV,
  Mono,
  PageHeader,
  Panel,
  SignalNote,
} from "@/components/rag/common";

export const Route = createFileRoute("/inspector")({
  head: () => ({
    meta: [
      { title: "Retrieval inspector — RAGForge" },
      {
        name: "description",
        content:
          "Ranked retrieval hits with sparse, dense, RRF and rerank signals shown separately.",
      },
      { property: "og:title", content: "Retrieval inspector — RAGForge" },
      {
        property: "og:description",
        content:
          "Ranked retrieval hits with sparse, dense, RRF and rerank signals shown separately.",
      },
    ],
  }),
  component: InspectorPage,
});

function InspectorPage() {
  const { options, retrieval } = useQueryState();
  const m = useMutation({
    mutationFn: api.retrieval,
    onSuccess: (r) => setQueryState({ retrieval: r }),
  });

  return (
    <>
      <PageHeader
        title="Retrieval inspector"
        description="Run retrieval without generation and see exactly what the retriever returns, in rank order."
      />
      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <Panel title="Query & options" className="self-start lg:sticky lg:top-6">
          <QueryControls
            busy={m.isPending}
            submitLabel="Retrieve"
            onSubmit={() => m.mutate(options)}
          />
          <p className="mt-3 text-xs text-muted-foreground">
            Same query and options as{" "}
            <Link to="/ask" className="text-primary hover:underline">
              Ask
            </Link>
            .
          </p>
        </Panel>
        <div className="space-y-4" aria-live="polite" aria-busy={m.isPending}>
          <div className="rounded-md border bg-muted/40 p-3">
            <SignalNote />
          </div>
          {m.isPending && (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-28" />
              ))}
            </div>
          )}
          {m.isError && <ErrorState error={m.error} onRetry={() => m.mutate(options)} />}
          {!m.isPending && !retrieval && !m.isError && (
            <Empty title="No retrieval yet">
              Run a query here or on Ask to populate the inspector.
            </Empty>
          )}
          {!m.isPending && retrieval && (
            <>
              <p className="text-sm text-muted-foreground">
                {retrieval.hits.length} hits for{" "}
                <Mono className="text-foreground">“{retrieval.query}”</Mono>
                {retrieval.mode && (
                  <>
                    {" "}
                    · mode <Mono>{retrieval.mode}</Mono>
                  </>
                )}
              </p>
              {retrieval.hits.length === 0 ? (
                <Empty title="No chunks retrieved">
                  Try a different mode, a larger top_k, or remove the document filter.
                </Empty>
              ) : (
                <ol className="space-y-2">
                  {retrieval.hits.map((h) => (
                    <HitCard key={`${h.rank}-${h.chunk_id}`} hit={h} />
                  ))}
                </ol>
              )}
              {retrieval.diagnostics && (
                <Panel title="Diagnostics">
                  <KV data={retrieval.diagnostics} />
                </Panel>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
