import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { ChevronDown } from "lucide-react";
import type { Hit } from "@/lib/api/types";
import { Mono, ScoreGrid } from "./common";

export function HitCard({ hit }: { hit: Hit }) {
  const [open, setOpen] = useState(false);
  const id = `hit-${hit.rank}`;
  return (
    <li className="rounded-md border bg-card">
      <div className="flex flex-wrap items-start gap-3 p-3">
        <span className="font-mono text-sm font-bold text-primary" aria-label={`Rank ${hit.rank}`}>
          #{hit.rank}
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{hit.title ?? "(untitled)"}</p>
          <p className="text-xs text-muted-foreground">
            doc <Mono>{hit.document_id}</Mono> · chunk <Mono>{hit.chunk_id}</Mono>
            {hit.start_char != null && (
              <>
                {" "}
                · chars{" "}
                <Mono>
                  {hit.start_char}–{hit.end_char}
                </Mono>
              </>
            )}
          </p>
        </div>
        <div className="w-full sm:w-72">
          <ScoreGrid scores={hit.scores} compact />
        </div>
      </div>
      <div className="border-t px-3 py-2">
        <p
          className={
            open ? "whitespace-pre-wrap text-sm" : "line-clamp-2 text-sm text-muted-foreground"
          }
          id={id}
        >
          {hit.text}
        </p>
        <div className="mt-2 flex flex-wrap gap-3 text-xs">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            aria-expanded={open}
            aria-controls={id}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            <ChevronDown className={`size-3.5 transition ${open ? "rotate-180" : ""}`} />{" "}
            {open ? "Collapse" : "Show exact chunk text"}
          </button>
          {hit.document_id && (
            <Link
              to="/documents"
              search={{ id: hit.document_id }}
              className="font-medium text-primary hover:underline"
            >
              Open source document →
            </Link>
          )}
        </div>
      </div>
    </li>
  );
}
