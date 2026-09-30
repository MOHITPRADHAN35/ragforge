import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Copy, FileJson, X } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Empty, fmt, KV, Mono, PageHeader, Panel, Tag } from "@/components/rag/common";
import {
  JUDGE_KEYS,
  loadStoredReport,
  PROXY_KEYS,
  RETRIEVAL_KEYS,
  sha256,
  storeReport,
  type StoredReport,
} from "@/lib/eval-report";

export const Route = createFileRoute("/evaluation")({
  head: () => ({
    meta: [
      { title: "Evaluation & experiments — RAGForge" },
      {
        name: "description",
        content:
          "Configure retrieval experiments and review Recall@K, MRR@K and nDCG@K reports with reproducibility hashes.",
      },
      { property: "og:title", content: "Evaluation & experiments — RAGForge" },
      {
        property: "og:description",
        content:
          "Configure retrieval experiments and review Recall@K, MRR@K and nDCG@K reports with reproducibility hashes.",
      },
    ],
  }),
  component: EvaluationPage,
});

type Dataset = { name: string; sha: string; count: number };

function EvaluationPage() {
  const [report, setReport] = useState<StoredReport | null>(null);
  useEffect(() => setReport(loadStoredReport()), []);
  return (
    <>
      <PageHeader
        title="Evaluation & experiments"
        description="The API does not run evaluations. Configure a run here, execute it with the RAGForge CLI, then load the resulting report JSON. Nothing below is estimated or generated in the browser."
      />
      <div className="grid gap-4 xl:grid-cols-[24rem_1fr]">
        <ConfigPanel />
        <div className="space-y-4">
          <ReportLoader
            onLoad={(r) => {
              setReport(r);
              storeReport(r);
            }}
            onClear={() => {
              setReport(null);
              storeReport(null);
            }}
            hasReport={!!report}
          />
          {report ? (
            <ReportView r={report} />
          ) : (
            <Empty title="No report loaded">
              Load a report JSON to see metrics, reproducibility details and comparisons.
            </Empty>
          )}
        </div>
      </div>
    </>
  );
}

function ConfigPanel() {
  const [ds, setDs] = useState<Dataset | null>(null);
  const [dsErr, setDsErr] = useState<string | null>(null);
  const [modes, setModes] = useState<string[]>(["sparse", "hybrid"]);
  const [chunkSizes, setChunkSizes] = useState("256, 512");
  const [overlaps, setOverlaps] = useState("32");
  const [topK, setTopK] = useState("5, 10");
  const [baseline, setBaseline] = useState("baseline");

  const list = (s: string) =>
    s
      .split(",")
      .map((x) => Number(x.trim()))
      .filter((n) => Number.isFinite(n) && n > 0);
  const config = {
    dataset: ds?.name ?? "<path/to/dataset.jsonl>",
    dataset_sha256: ds?.sha,
    baseline_label: baseline || undefined,
    grid: {
      mode: modes,
      chunk_size: list(chunkSizes),
      chunk_overlap: list(overlaps),
      top_k: list(topK),
    },
  };
  const runs = modes.length * list(chunkSizes).length * list(overlaps).length * list(topK).length;
  const json = JSON.stringify(config, null, 2);

  const onDataset = async (f?: File) => {
    setDsErr(null);
    setDs(null);
    if (!f) return;
    const text = await f.text();
    let count = 0;
    try {
      if (f.name.endsWith(".jsonl"))
        count = text
          .split("\n")
          .filter((l) => l.trim())
          .map((l) => JSON.parse(l)).length;
      else {
        const j = JSON.parse(text);
        count = Array.isArray(j)
          ? j.length
          : Array.isArray(j.queries)
            ? j.queries.length
            : Array.isArray(j.examples)
              ? j.examples.length
              : 0;
      }
    } catch {
      return setDsErr("Could not parse dataset — expected JSON or JSONL.");
    }
    setDs({ name: f.name, sha: await sha256(text), count });
  };

  return (
    <Panel title="Experiment configuration" className="self-start">
      <div className="space-y-4">
        <div>
          <Label htmlFor="ds">Dataset (local file)</Label>
          <Input
            id="ds"
            type="file"
            accept=".json,.jsonl"
            className="mt-1.5"
            onChange={(e) => onDataset(e.target.files?.[0])}
          />
          <p className="mt-1 text-xs text-muted-foreground">
            Hashed in your browser; not uploaded.
          </p>
          {dsErr && (
            <p role="alert" className="mt-1 text-sm text-destructive">
              {dsErr}
            </p>
          )}
          {ds && (
            <p className="mt-1 text-xs">
              {ds.count} queries · sha256 <Mono>{ds.sha.slice(0, 16)}…</Mono>
            </p>
          )}
        </div>
        <fieldset>
          <legend className="text-sm font-medium">Retrieval modes</legend>
          <div className="mt-1.5 flex gap-3">
            {["sparse", "dense", "hybrid"].map((m) => (
              <label key={m} className="flex items-center gap-1.5 font-mono text-sm">
                <input
                  type="checkbox"
                  checked={modes.includes(m)}
                  onChange={(e) =>
                    setModes(e.target.checked ? [...modes, m] : modes.filter((x) => x !== m))
                  }
                />{" "}
                {m}
              </label>
            ))}
          </div>
        </fieldset>
        {[
          ["cs", "Chunk sizes", chunkSizes, setChunkSizes],
          ["ov", "Overlaps", overlaps, setOverlaps],
          ["tk", "top_k values", topK, setTopK],
        ].map(([id, l, v, set]) => (
          <div key={id as string}>
            <Label htmlFor={id as string}>
              {l as string} <span className="text-muted-foreground">(comma-separated)</span>
            </Label>
            <Input
              id={id as string}
              value={v as string}
              onChange={(e) => (set as (s: string) => void)(e.target.value)}
              className="mt-1.5 font-mono"
            />
          </div>
        ))}
        <div>
          <Label htmlFor="bl">Baseline label</Label>
          <Input
            id="bl"
            value={baseline}
            maxLength={80}
            onChange={(e) => setBaseline(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <div>
          <div className="mb-1 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase text-muted-foreground">
              Grid config · {runs} runs
            </span>
            <Button
              size="sm"
              variant="ghost"
              onClick={() =>
                navigator.clipboard.writeText(json).then(() => toast.success("Config copied"))
              }
            >
              <Copy className="size-3.5" /> Copy
            </Button>
          </div>
          <pre className="max-h-64 overflow-auto rounded border bg-muted/50 p-2 font-mono text-xs">
            {json}
          </pre>
          <p className="mt-1 text-xs text-muted-foreground">
            Pass this config to the RAGForge evaluation CLI, then load its report on the right.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function ReportLoader({
  onLoad,
  onClear,
  hasReport,
}: {
  onLoad: (r: StoredReport) => void;
  onClear: () => void;
  hasReport: boolean;
}) {
  const [err, setErr] = useState<string | null>(null);
  return (
    <Panel
      title="Report"
      aside={
        hasReport && (
          <Button size="sm" variant="ghost" onClick={onClear}>
            <X className="size-3.5" /> Clear
          </Button>
        )
      }
    >
      <Label htmlFor="rep" className="flex items-center gap-2">
        <FileJson className="size-4" /> Load report JSON
      </Label>
      <Input
        id="rep"
        type="file"
        accept=".json"
        className="mt-1.5"
        onChange={async (e) => {
          setErr(null);
          const f = e.target.files?.[0];
          if (!f) return;
          try {
            const j = JSON.parse(await f.text());
            if (!j || typeof j !== "object" || Array.isArray(j)) throw 0;
            onLoad({ ...j, _filename: f.name, _loaded_at: new Date().toISOString() });
          } catch {
            setErr("Not a valid report JSON object.");
          }
        }}
      />
      {err && (
        <p role="alert" className="mt-1 text-sm text-destructive">
          {err}
        </p>
      )}
    </Panel>
  );
}

function pickMetrics(obj: Record<string, unknown> | undefined, re: RegExp) {
  if (!obj) return {};
  return Object.fromEntries(
    Object.entries(obj).filter(([k, v]) => re.test(k) && (typeof v === "number" || v === null)),
  ) as Record<string, number | null>;
}

function MetricTable({
  metrics,
  empty,
}: {
  metrics: Record<string, number | null>;
  empty: string;
}) {
  const e = Object.entries(metrics);
  if (!e.length) return <p className="text-sm text-muted-foreground">{empty}</p>;
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded border bg-border sm:grid-cols-3">
      {e.map(([k, v]) => (
        <div key={k} className="bg-card p-3">
          <dt className="font-mono text-xs text-muted-foreground">{k}</dt>
          <dd className="font-mono text-lg font-semibold">
            {v == null ? (
              <span className="text-sm text-muted-foreground">unavailable</span>
            ) : (
              fmt(v, 3)
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

function flattenRunMetrics(m: unknown): Record<string, number | null> {
  if (typeof m !== "object" || m === null) return {};
  const res: Record<string, number | null> = {};
  const metricsObj = (m as { metrics?: unknown }).metrics ?? m;
  if (typeof metricsObj === "object" && metricsObj !== null) {
    for (const [k, v] of Object.entries(metricsObj)) {
      if (typeof v === "number" || v === null) {
        res[k] = v;
      } else if (typeof v === "object" && v !== null) {
        for (const [subK, subV] of Object.entries(v)) {
          if (typeof subV === "number" || subV === null) {
            res[`${subK}@${k}`] = subV;
          }
        }
      }
    }
  }
  return res;
}

function ReportView({ r }: { r: StoredReport }) {
  const counts = (typeof r.counts === "object" && r.counts !== null ? r.counts : {}) as Record<
    string,
    unknown
  >;
  const judgeObj = (typeof r.judge === "object" && r.judge !== null ? r.judge : {}) as Record<
    string,
    unknown
  >;
  const datasetObj = (
    typeof r.dataset === "object" && r.dataset !== null ? r.dataset : {}
  ) as Record<string, unknown>;
  const firstRun =
    Array.isArray(r.runs) && r.runs[0] && typeof r.runs[0] === "object"
      ? (r.runs[0] as Record<string, unknown>)
      : null;
  const firstMetrics =
    firstRun && typeof firstRun.metrics === "object" && firstRun.metrics !== null
      ? (firstRun.metrics as Record<string, unknown>)
      : null;
  const innerMetrics =
    firstMetrics && typeof firstMetrics.metrics === "object" && firstMetrics.metrics !== null
      ? (firstMetrics.metrics as Record<string, unknown>)
      : null;
  const firstK = innerMetrics
    ? (Object.values(innerMetrics)[0] as Record<string, unknown> | undefined)
    : undefined;

  const rMetrics = (typeof r.metrics === "object" && r.metrics !== null ? r.metrics : {}) as Record<
    string,
    unknown
  >;
  const rRet = (
    typeof r.retrieval_metrics === "object" && r.retrieval_metrics !== null
      ? r.retrieval_metrics
      : {}
  ) as Record<string, unknown>;
  const rGen = (
    typeof r.generation_metrics === "object" && r.generation_metrics !== null
      ? r.generation_metrics
      : {}
  ) as Record<string, unknown>;
  const rJudge = (
    typeof r.judge_metrics === "object" && r.judge_metrics !== null ? r.judge_metrics : {}
  ) as Record<string, unknown>;

  const metrics: Record<string, unknown> = {
    ...flattenRunMetrics(firstRun?.metrics),
    ...rMetrics,
    ...rRet,
    ...rGen,
    ...rJudge,
  };
  const retrieval = pickMetrics(metrics, RETRIEVAL_KEYS);
  const proxies = pickMetrics(metrics, PROXY_KEYS);
  const judge = pickMetrics(metrics, JUDGE_KEYS);
  const evaluated = (r.evaluated_queries ??
    r.num_evaluated ??
    counts.evaluated ??
    firstK?.evaluated_queries) as React.ReactNode;
  const unavailable = (r.unavailable_queries ??
    r.num_unavailable ??
    counts.unavailable ??
    firstK?.unavailable_queries) as React.ReactNode;
  const judgeConfigured = (r.judge_configured ?? judgeObj.configured) as boolean | undefined;

  const runId = (r.run_id ?? firstRun?.run_id) as string | undefined;
  const datasetSha = (r.dataset_sha256 ?? datasetObj.sha256) as string | undefined;
  const timestamp = (r.timestamp ?? r.created_at) as string | undefined;
  const baseline = (r.baseline_label ?? r.baseline ?? firstRun?.baseline) as string | undefined;

  const rows: Record<string, unknown>[] = useMemo(() => {
    const rawRows = Array.isArray(r.runs)
      ? (r.runs as Record<string, unknown>[])
      : Array.isArray(r.results)
        ? (r.results as Record<string, unknown>[])
        : Array.isArray(r.comparisons)
          ? (r.comparisons as Record<string, unknown>[])
          : [];
    return rawRows.map((row) => ({
      ...row,
      metrics: {
        ...(typeof row.metrics === "object" && row.metrics !== null
          ? (row.metrics as Record<string, unknown>)
          : {}),
        ...flattenRunMetrics(row.metrics),
      },
    }));
  }, [r]);

  const dims = [
    "architecture",
    "mode",
    "embedding_mode",
    "chunking_strategy",
    "chunk_size",
    "chunk_overlap",
    "top_k",
    "reranker",
  ].filter((d) =>
    rows.some((x) => {
      const cfg =
        typeof x.config === "object" && x.config !== null
          ? (x.config as Record<string, unknown>)
          : {};
      return x[d] !== undefined || cfg[d] !== undefined;
    }),
  );
  const metricCols = [
    ...new Set(
      rows.flatMap((x) => {
        const m =
          typeof x.metrics === "object" && x.metrics !== null
            ? (x.metrics as Record<string, unknown>)
            : x;
        return Object.keys(m).filter((k) => RETRIEVAL_KEYS.test(k));
      }),
    ),
  ];

  return (
    <>
      <Panel title="Reproducibility">
        <dl className="grid gap-x-4 gap-y-2 text-sm sm:grid-cols-2">
          {(
            [
              ["Run ID", runId],
              ["Timestamp", timestamp],
              ["Baseline", baseline],
              ["Dataset SHA-256", datasetSha],
              ["Config SHA-256", r.config_sha256],
              ["Source file", r._filename],
            ] as const
          ).map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted-foreground">{k}</dt>
              <dd>
                <Mono>{(v as string | undefined) ?? "not in report"}</Mono>
              </dd>
            </div>
          ))}
        </dl>
        {(r.config || r.environment) && (
          <details className="mt-3">
            <summary className="cursor-pointer text-sm font-medium">Config & environment</summary>
            <div className="mt-2">
              <KV data={{ ...(r.config ?? {}), ...(r.environment ?? {}) }} />
            </div>
          </details>
        )}
      </Panel>

      <Panel
        title="Retrieval metrics"
        aside={
          <span className="text-xs text-muted-foreground">
            evaluated <Mono>{evaluated ?? "?"}</Mono> · unavailable{" "}
            <Mono>{unavailable ?? "?"}</Mono>
          </span>
        }
      >
        <MetricTable metrics={retrieval} empty="No Recall/MRR/nDCG values in this report." />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Lexical proxies & evidence overlap" aside={<Tag>no judge</Tag>}>
          <p className="mb-3 text-xs text-muted-foreground">
            Computed from token or span overlap. Cheap and deterministic, but they are proxies, not
            measures of correctness.
          </p>
          <MetricTable metrics={proxies} empty="No proxy metrics in this report." />
        </Panel>
        <Panel
          title="Judge-dependent metrics"
          aside={
            <Tag tone={judgeConfigured ? "primary" : "warning"}>
              {judgeConfigured ? "judge configured" : "judge not reported"}
            </Tag>
          }
        >
          <p className="mb-3 text-xs text-muted-foreground">
            Faithfulness, answer relevance and citation correctness need an LLM judge. Values depend
            on the judge model.
          </p>
          <MetricTable metrics={judge} empty="Not available — no judge results in this report." />
        </Panel>
      </div>

      {rows.length > 0 && (
        <Panel title={`Comparison (${rows.length} runs)`}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <caption className="sr-only">Experiment comparison</caption>
              <thead>
                <tr className="border-b text-left">
                  {[...dims, ...metricCols].map((c) => (
                    <th
                      key={c}
                      scope="col"
                      className="px-2 py-1.5 font-mono text-xs font-medium text-muted-foreground"
                    >
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((x, i) => {
                  const cfg =
                    typeof x.config === "object" && x.config !== null
                      ? (x.config as Record<string, unknown>)
                      : {};
                  const m =
                    typeof x.metrics === "object" && x.metrics !== null
                      ? (x.metrics as Record<string, unknown>)
                      : x;
                  return (
                    <tr key={i} className="border-b last:border-0">
                      {dims.map((d) => (
                        <td key={d} className="px-2 py-1.5 font-mono text-xs">
                          {String(x[d] ?? cfg[d] ?? "—")}
                        </td>
                      ))}
                      {metricCols.map((c) => {
                        const v = m[c];
                        return (
                          <td key={c} className="px-2 py-1.5 font-mono text-xs">
                            {typeof v === "number" ? fmt(v, 3) : "—"}
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  );
}
