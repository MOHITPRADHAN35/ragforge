import { useSyncExternalStore } from "react";
import type { QueryOptions, QueryResult, RetrievalResult } from "./api/types";

// In-memory session state so query + options + results survive navigating
// between Ask and the Retrieval inspector.
interface State {
  options: QueryOptions;
  answer: QueryResult | null;
  retrieval: RetrievalResult | null;
}

let state: State = {
  options: {
    query: "",
    mode: "hybrid",
    top_k: 5,
    document_ids: [],
    rerank: false,
    rewrite: false,
    hyde: false,
    compress: false,
  },
  answer: null,
  retrieval: null,
};
const subs = new Set<() => void>();

export function setQueryState(patch: Partial<State> | ((s: State) => Partial<State>)) {
  const p = typeof patch === "function" ? patch(state) : patch;
  state = { ...state, ...p };
  subs.forEach((f) => f());
}
export function setOptions(p: Partial<QueryOptions>) {
  setQueryState((s) => ({ options: { ...s.options, ...p } }));
}
export function useQueryState() {
  return useSyncExternalStore(
    (f) => (subs.add(f), () => subs.delete(f)),
    () => state,
    () => state,
  );
}
