"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
const PAGE_SIZE = 20;

type AgentRun = {
  agent_id: string;
  request_id: string;
  status: string;
  duration_ms: number;
  input_hash: string;
  prompt_count: number;
  image_count: number;
  error: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
};

type AgentRunResponse = {
  runs: AgentRun[];
  total: number;
  limit: number;
  offset: number;
};

export default function AgentRunDashboard(): JSX.Element {
  const [runs, setRuns] = useState<AgentRun[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [agentId, setAgentId] = useState("");
  const [status, setStatus] = useState("");
  const [since, setSince] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const totalPages = useMemo(() => Math.ceil(total / PAGE_SIZE) || 1, [total]);
  const currentPage = useMemo(() => Math.floor(offset / PAGE_SIZE) + 1, [offset]);

  useEffect(() => {
    void fetchRuns(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchRuns = (nextOffset: number) =>
    startTransition(async () => {
      setError(null);
      const params = new URLSearchParams({
        limit: PAGE_SIZE.toString(),
        offset: nextOffset.toString(),
      });
      const trimmedAgent = agentId.trim();
      if (trimmedAgent) params.set("agent_id", trimmedAgent);
      if (status) params.set("status", status);
      if (since) {
        const sinceDate = new Date(since);
        if (!Number.isNaN(sinceDate.getTime())) {
          params.set("since", sinceDate.toISOString());
        }
      }

      try {
        const response = await fetch(`${API_BASE_URL}/agent-runs?${params.toString()}`);
        if (!response.ok) {
          const detail = await safeParseError(response);
          throw new Error(detail ?? "获取执行记录失败，请稍后再试");
        }
        const payload = (await response.json()) as AgentRunResponse;
        setRuns(payload.runs);
        setTotal(payload.total);
        setOffset(payload.offset);
      } catch (err) {
        setError(err instanceof Error ? err.message : "获取执行记录失败，请稍后再试");
      }
    });

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void fetchRuns(0);
  };

  const handleReset = () => {
    setAgentId("");
    setStatus("");
    setSince("");
    void fetchRuns(0);
  };

  const goToPage = (page: number) => {
    const nextOffset = Math.max(0, (page - 1) * PAGE_SIZE);
    void fetchRuns(nextOffset);
  };

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-8 px-4 py-12">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Observability</p>
        <h1 className="text-3xl font-semibold tracking-tight">Agent 执行记录面板</h1>
        <p className="text-muted-foreground">
          查看各 Agent 最近的执行历史，支持按 Agent ID、状态与时间过滤，辅助定位异常与耗时问题。
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="grid gap-4 rounded-2xl border border-border bg-card/40 p-6 shadow-sm backdrop-blur"
      >
        <div className="grid gap-2 sm:grid-cols-3 sm:gap-4">
          <div className="grid gap-2">
            <Label htmlFor="agentId">Agent ID</Label>
            <Input
              id="agentId"
              placeholder="例如：CollageAgent"
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="status">执行状态</Label>
            <select
              id="status"
              className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              value={status}
              onChange={(event) => setStatus(event.target.value)}
            >
              <option value="">全部</option>
              <option value="success">success</option>
              <option value="failed">failed</option>
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="since">时间下限</Label>
            <Input
              id="since"
              type="datetime-local"
              value={since}
              onChange={(event) => setSince(event.target.value)}
            />
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-3">
          <Button type="submit" disabled={isPending}>
            {isPending ? "查询中…" : "查询"}
          </Button>
          <Button type="button" variant="outline" onClick={handleReset} disabled={isPending}>
            重置
          </Button>
          <span className="text-sm text-muted-foreground">
            共 {total} 条记录，当前第 {currentPage} / {totalPages} 页。
          </span>
        </div>
      </form>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-semibold">执行记录</h2>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => goToPage(Math.max(1, currentPage - 1))}
              disabled={isPending || currentPage <= 1}
            >
              上一页
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => goToPage(currentPage + 1)}
              disabled={isPending || currentPage >= totalPages}
            >
              下一页
            </Button>
          </div>
        </div>

        <div className="overflow-x-auto rounded-2xl border border-border bg-card/50 shadow-sm">
          <table className="w-full min-w-max table-auto text-sm">
            <thead className="bg-muted/70 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">Agent</th>
                <th className="px-4 py-3 text-left">Request ID</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">耗时 (ms)</th>
                <th className="px-4 py-3 text-left">Prompts</th>
                <th className="px-4 py-3 text-left">Images</th>
                <th className="px-4 py-3 text-left">时间</th>
                <th className="px-4 py-3 text-left">异常</th>
                <th className="px-4 py-3 text-left">Metadata</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-6 text-center text-muted-foreground">
                    {isPending ? "数据加载中…" : "暂无符合条件的执行记录"}
                  </td>
                </tr>
              ) : (
                runs.map((run) => (
                  <tr key={run.request_id} className="border-t border-border/60">
                    <td className="px-4 py-3 font-medium text-foreground">{run.agent_id}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{run.request_id}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-3">{run.duration_ms.toFixed(1)}</td>
                    <td className="px-4 py-3">{run.prompt_count}</td>
                    <td className="px-4 py-3">{run.image_count}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatDate(run.created_at)}
                    </td>
                    <td className="px-4 py-3 text-xs text-destructive/80">
                      {run.error ? truncate(run.error, 60) : "-"}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatMetadata(run.metadata)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function StatusBadge({ status }: { status: string }): JSX.Element {
  const color = status === "success" ? "bg-emerald-500/20 text-emerald-600" : "bg-destructive/10 text-destructive";
  return <span className={`rounded-full px-3 py-1 text-xs font-medium ${color}`}>{status}</span>;
}

function formatDate(value: string): string {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  } catch {
    return value;
  }
}

function truncate(value: string, length: number): string {
  if (value.length <= length) return value;
  return `${value.slice(0, length)}…`;
}

function formatMetadata(metadata: Record<string, unknown>): string {
  const entries = Object.entries(metadata).filter(([, v]) => v !== null && v !== undefined);
  if (!entries.length) return "-";
  return entries
    .slice(0, 4)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(" | ");
}

async function safeParseError(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? null;
  } catch (error) {
    console.warn("Failed to parse agent run API error", error);
    return null;
  }
}
