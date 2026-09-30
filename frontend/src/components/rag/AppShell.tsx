import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import {
  FileText,
  FlaskConical,
  LayoutGrid,
  MessageSquareQuote,
  ScanSearch,
  Menu,
  X,
} from "lucide-react";
import { api, isMockMode, setMockMode } from "@/lib/api/client";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Overview", icon: LayoutGrid },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/ask", label: "Ask", icon: MessageSquareQuote },
  { to: "/inspector", label: "Retrieval inspector", icon: ScanSearch },
  { to: "/evaluation", label: "Evaluation", icon: FlaskConical },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const [mock, setMock] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => setMock(isMockMode()), []);
  const health = useQuery({
    queryKey: ["health", mock],
    queryFn: api.health,
    retry: 0,
    refetchInterval: 30_000,
  });

  const nav = (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {NAV.map(({ to, label, icon: Icon }) => (
        <Link
          key={to}
          to={to}
          onClick={() => setOpen(false)}
          className="flex items-center gap-2.5 rounded px-2.5 py-2 text-sm text-sidebar-foreground/75 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
          activeProps={{
            className: "bg-sidebar-accent !text-sidebar-accent-foreground font-medium",
          }}
          activeOptions={{ exact: to === "/" }}
        >
          <Icon className="size-4" aria-hidden /> {label}
        </Link>
      ))}
    </nav>
  );

  const sidebarBody = (
    <>
      <div className="mb-6 flex items-center gap-2 px-2">
        <div className="grid size-7 place-items-center rounded bg-sidebar-primary font-mono text-xs font-bold text-sidebar-primary-foreground">
          RF
        </div>
        <div>
          <p className="text-sm font-semibold text-sidebar-accent-foreground">RAGForge</p>
          <p className="font-mono text-[0.65rem] text-sidebar-foreground/60">
            evaluation-first RAG
          </p>
        </div>
      </div>
      {nav}
      <div className="mt-auto space-y-3 border-t border-sidebar-border px-2 pt-4 text-xs">
        <div className="flex items-center gap-2" role="status" aria-live="polite">
          <span
            className={cn(
              "size-2 rounded-full",
              health.isSuccess
                ? "bg-success"
                : health.isError
                  ? "bg-destructive"
                  : "bg-muted-foreground",
            )}
            aria-hidden
          />
          <span className="text-sidebar-foreground/80">
            API {health.isSuccess ? "reachable" : health.isError ? "unreachable" : "checking…"}
          </span>
        </div>
        <label className="flex items-center justify-between gap-2 text-sidebar-foreground/80">
          Mock adapter (dev)
          <Switch
            checked={mock}
            onCheckedChange={(v) => setMockMode(v)}
            aria-label="Toggle mock adapter"
          />
        </label>
      </div>
    </>
  );

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col bg-sidebar p-3 lg:flex">
        {sidebarBody}
      </aside>
      <header className="sticky top-0 z-30 flex items-center justify-between border-b bg-sidebar px-4 py-2 lg:hidden">
        <span className="font-semibold text-sidebar-accent-foreground">RAGForge</span>
        <button
          onClick={() => setOpen(true)}
          aria-label="Open navigation"
          className="text-sidebar-foreground"
        >
          <Menu className="size-5" />
        </button>
      </header>
      {open && (
        <div
          className="fixed inset-0 z-40 lg:hidden"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
        >
          <div className="absolute inset-0 bg-foreground/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 flex w-64 flex-col bg-sidebar p-3">
            <button
              onClick={() => setOpen(false)}
              aria-label="Close navigation"
              className="mb-2 self-end text-sidebar-foreground"
            >
              <X className="size-5" />
            </button>
            {sidebarBody}
          </aside>
        </div>
      )}
      <div className="lg:pl-60">
        {mock && (
          <div
            role="status"
            className="border-b border-warning/40 bg-warning/10 px-4 py-2 text-center text-xs font-medium text-warning"
          >
            MOCK DATA — responses are fabricated locally for UI development and are not RAGForge
            backend output.
          </div>
        )}
        <main id="main" className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
