import { useCallback, useEffect, useRef, useState } from "react";
import type { Repository, RunBrief } from "./types";

type Page = {
  runs: RunBrief[];
  repositories: Repository[];
  total: number;
  has_more: boolean;
  next_cursor: string | null;
  index_status?: {state: string; message?: string};
};
const empty: Page = { runs: [], repositories: [], total: 0, has_more: false, next_cursor: null };

export function useCatalogue(kind: "records" | "repositories", query = "", repository = "", revision = "", enabled = true) {
  const [page, setPage] = useState<Page>(empty);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const active = useRef<AbortController | null>(null);
  const busy = useRef(false);
  const fetchPage = useCallback(async (cursor: string | null, token: number) => {
    if (busy.current) return;
    busy.current = true;
    const controller = new AbortController(); active.current = controller;
    setLoading(true); setError("");
    try {
      const params = new URLSearchParams({ kind, query, repository, limit: "50" });
      if (cursor) params.set("cursor", cursor);
      const response = await fetch(`/api/catalogue?${params}`, { signal: controller.signal });
      if (!response.ok) throw new Error(`读取目录失败（${response.status}）`);
      const data = await response.json() as Page;
      if (generation.current !== token) return;
      const unique = <T extends { id: string }>(items: T[]) => [...new Map(items.map(item => [item.id, item])).values()];
      setPage(previous => cursor ? { ...data, runs: unique([...previous.runs, ...data.runs]), repositories: unique([...previous.repositories, ...data.repositories]) } : data);
    } catch (e) {
      if (!controller.signal.aborted && generation.current === token) setError(e instanceof Error ? e.message : "读取目录失败");
    } finally {
      if (generation.current === token) { busy.current = false; setLoading(false); }
    }
  }, [kind, query, repository]);
  useEffect(() => {
    const token = ++generation.current;
    active.current?.abort(); busy.current = false; setPage(empty); setLoading(enabled); setError("");
    if (!enabled) return;
    const timer = setTimeout(() => void fetchPage(null, token), query ? 180 : 0);
    return () => { clearTimeout(timer); active.current?.abort(); generation.current++; busy.current = false; };
  }, [fetchPage, revision, enabled]);
  return { ...page, loading, error, loadMore: () => fetchPage(page.next_cursor, generation.current), retry: () => fetchPage(null, generation.current) };
}
