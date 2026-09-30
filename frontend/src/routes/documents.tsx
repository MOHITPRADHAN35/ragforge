import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { z } from "zod";
import { toast } from "sonner";
import { Trash2, Upload, X } from "lucide-react";
import { api } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  documentsQuery,
  Empty,
  ErrorState,
  KV,
  Mono,
  PageHeader,
  Panel,
  useCapabilities,
} from "@/components/rag/common";

export const Route = createFileRoute("/documents")({
  validateSearch: z.object({ id: z.string().optional() }),
  head: () => ({
    meta: [
      { title: "Documents — RAGForge" },
      {
        name: "description",
        content: "Upload, inspect and delete documents in the RAGForge index.",
      },
      { property: "og:title", content: "Documents — RAGForge" },
      {
        property: "og:description",
        content: "Upload, inspect and delete documents in the RAGForge index.",
      },
    ],
  }),
  component: DocumentsPage,
});

const textSchema = z.object({
  title: z.string().trim().min(1, "Title is required").max(300),
  text: z.string().trim().min(1, "Text is required").max(2_000_000),
});

function DocumentsPage() {
  const { id } = Route.useSearch();
  const navigate = useNavigate({ from: "/documents" });
  const docs = useQuery(documentsQuery);
  const qc = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<{ id: string; title: string } | null>(null);

  const del = useMutation({
    mutationFn: (docId: string) => api.deleteDocument(docId),
    onSuccess: (_d, docId) => {
      toast.success("Document deleted");
      qc.invalidateQueries({ queryKey: ["documents"] });
      if (docId === id) navigate({ search: {} });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Delete failed"),
  });

  return (
    <>
      <PageHeader
        title="Documents"
        description="Everything the retriever can cite. Deleting a document removes its chunks from the index."
      />
      <div className="grid gap-4 lg:grid-cols-[22rem_1fr]">
        <div className="space-y-4">
          <UploadPanel />
          <TextPanel />
        </div>
        <div className="space-y-4">
          <Panel title={`Indexed documents${docs.data ? ` (${docs.data.length})` : ""}`}>
            {docs.isLoading && (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-12" />
                ))}
              </div>
            )}
            {docs.isError && <ErrorState error={docs.error} onRetry={() => docs.refetch()} />}
            {docs.data?.length === 0 && (
              <Empty title="No documents yet">
                Upload a file or paste text to build the index.
              </Empty>
            )}
            {!!docs.data?.length && (
              <ul className="divide-y">
                {docs.data.map((d) => (
                  <li
                    key={d.document_id}
                    className={`flex items-center gap-3 py-2 ${d.document_id === id ? "bg-accent/50 -mx-2 px-2 rounded" : ""}`}
                  >
                    <button
                      className="min-w-0 flex-1 text-left"
                      onClick={() => navigate({ search: { id: d.document_id } })}
                      aria-current={d.document_id === id}
                    >
                      <p className="truncate text-sm font-medium hover:text-primary">{d.title}</p>
                      <p className="text-xs text-muted-foreground">
                        <Mono>{d.document_id}</Mono> · {d.chunk_count ?? "?"} chunks
                      </p>
                    </button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Delete ${d.title}`}
                      onClick={() => setPendingDelete({ id: d.document_id, title: d.title })}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
          {id && <DocumentDetail id={id} onClose={() => navigate({ search: {} })} />}
        </div>
      </div>

      <AlertDialog open={!!pendingDelete} onOpenChange={(o) => !o && setPendingDelete(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this document?</AlertDialogTitle>
            <AlertDialogDescription>
              “{pendingDelete?.title}” and all of its chunks will be removed from the index. This
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => pendingDelete && del.mutate(pendingDelete.id)}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}

function UploadPanel() {
  const caps = useCapabilities();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [progress, setProgress] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pdf = caps.data?.pdf_supported !== false;
  const exts = (caps.data?.supported_extensions as string[] | undefined) ?? [
    ".txt",
    ".md",
    ".html",
    ...(pdf ? [".pdf"] : []),
  ];
  const max = caps.data?.max_upload_bytes;

  const pick = (f: File | undefined) => {
    setError(null);
    if (!f) return setFile(null);
    const ext = "." + (f.name.split(".").pop() ?? "").toLowerCase();
    if (!exts.includes(ext)) {
      setFile(null);
      return setError(`Unsupported format “${ext}”. Allowed: ${exts.join(", ")}`);
    }
    if (max && f.size > max) {
      setFile(null);
      return setError(
        `File is ${(f.size / 1e6).toFixed(1)} MB; limit is ${(max / 1e6).toFixed(1)} MB.`,
      );
    }
    setFile(f);
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setProgress(0);
    setError(null);
    try {
      const d = await api.upload(file, title.trim() || undefined, setProgress);
      toast.success(`Indexed “${d.title}”`);
      setFile(null);
      setTitle("");
      if (input.current) input.current.value = "";
      qc.invalidateQueries({ queryKey: ["documents"] });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setProgress(null);
    }
  };

  return (
    <Panel title="Upload file">
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label htmlFor="file">File</Label>
          <Input
            ref={input}
            id="file"
            type="file"
            accept={exts.join(",")}
            className="mt-1.5"
            onChange={(e) => pick(e.target.files?.[0])}
            aria-describedby="file-h"
          />
          <p id="file-h" className="mt-1 text-xs text-muted-foreground">
            {exts.join(", ")}
            {max ? ` · max ${(max / 1e6).toFixed(1)} MB` : ""}
          </p>
        </div>
        <div>
          <Label htmlFor="up-title">
            Title <span className="text-muted-foreground">(optional)</span>
          </Label>
          <Input
            id="up-title"
            value={title}
            maxLength={300}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1.5"
          />
        </div>
        {progress != null && (
          <div role="status" aria-live="polite">
            <Progress value={progress} aria-label="Upload progress" />
            <p className="mt-1 font-mono text-xs">{progress}%</p>
          </div>
        )}
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <Button type="submit" disabled={!file || progress != null} className="w-full">
          <Upload className="size-4" /> Upload & index
        </Button>
      </form>
    </Panel>
  );
}

function TextPanel() {
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [meta, setMeta] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: (v: { title: string; text: string; metadata: Record<string, unknown> }) =>
      api.addText(v.title, v.text, v.metadata),
    onSuccess: (d) => {
      toast.success(`Indexed “${d.title}”`);
      setTitle("");
      setText("");
      setMeta("");
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e) => setErr(e instanceof Error ? e.message : "Failed"),
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    const p = textSchema.safeParse({ title, text });
    if (!p.success) return setErr(p.error.issues[0]?.message ?? "Invalid input");
    let metadata: Record<string, unknown> = {};
    if (meta.trim()) {
      try {
        metadata = JSON.parse(meta);
        if (typeof metadata !== "object" || Array.isArray(metadata) || !metadata) throw 0;
      } catch {
        return setErr('Metadata must be a JSON object, e.g. {"source":"wiki"}');
      }
    }
    m.mutate({ ...p.data, metadata });
  };
  return (
    <Panel title="Add plain text">
      <form onSubmit={submit} className="space-y-3">
        <div>
          <Label htmlFor="t-title">Title</Label>
          <Input
            id="t-title"
            value={title}
            maxLength={300}
            onChange={(e) => setTitle(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <div>
          <Label htmlFor="t-text">Text</Label>
          <Textarea
            id="t-text"
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="mt-1.5"
          />
        </div>
        <div>
          <Label htmlFor="t-meta">
            Metadata JSON <span className="text-muted-foreground">(optional)</span>
          </Label>
          <Textarea
            id="t-meta"
            rows={2}
            value={meta}
            onChange={(e) => setMeta(e.target.value)}
            className="mt-1.5 font-mono text-xs"
            placeholder='{"source": "handbook"}'
          />
        </div>
        {err && (
          <p role="alert" className="text-sm text-destructive">
            {err}
          </p>
        )}
        <Button type="submit" disabled={m.isPending} className="w-full">
          {m.isPending ? "Indexing…" : "Add document"}
        </Button>
      </form>
    </Panel>
  );
}

function DocumentDetail({ id, onClose }: { id: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["document", id], queryFn: () => api.getDocument(id), retry: 1 });
  return (
    <Panel
      title="Document detail"
      aside={
        <Button size="icon" variant="ghost" onClick={onClose} aria-label="Close detail">
          <X className="size-4" />
        </Button>
      }
    >
      {q.isLoading && <Skeleton className="h-40" />}
      {q.isError && <ErrorState error={q.error} onRetry={() => q.refetch()} />}
      {q.data && (
        <div className="space-y-4">
          <div>
            <h3 className="font-medium">{q.data.title}</h3>
            <p className="text-xs text-muted-foreground">
              <Mono>{q.data.document_id}</Mono> ·{" "}
              {q.data.chunk_count ?? q.data.chunks?.length ?? "?"} chunks
              {q.data.created_at ? ` · ${q.data.created_at}` : ""}
            </p>
          </div>
          <div>
            <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Metadata</h4>
            <KV data={q.data.metadata} />
          </div>
          {q.data.chunks?.length ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Chunks</h4>
              <ol className="max-h-[32rem] space-y-2 overflow-y-auto">
                {q.data.chunks.map((c) => (
                  <li key={c.chunk_id} className="rounded border p-2">
                    <p className="mb-1 text-xs text-muted-foreground">
                      <Mono>{c.chunk_id}</Mono>
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
                    <p className="whitespace-pre-wrap text-sm">{c.text}</p>
                  </li>
                ))}
              </ol>
            </div>
          ) : q.data.text ? (
            <div>
              <h4 className="mb-1 text-xs font-semibold uppercase text-muted-foreground">Text</h4>
              <p className="max-h-96 overflow-y-auto whitespace-pre-wrap rounded border p-2 text-sm">
                {q.data.text}
              </p>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              The API did not return chunk text for this document.
            </p>
          )}
        </div>
      )}
    </Panel>
  );
}
