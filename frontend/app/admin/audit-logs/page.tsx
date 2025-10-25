"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type AuditLog = {
  actor_type: string;
  actor_id: string;
  request_id: string;
  method: string;
  path: string;
  status_code: number;
  ip?: string | null;
  user_agent?: string | null;
  created_at: string;
  duration_ms?: number | null;
  req_bytes?: number | null;
  res_bytes?: number | null;
};

export default function AuditLogsAdmin(): JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [actorType, setActorType] = useState("");
  const [since, setSince] = useState("");
  const [method, setMethod] = useState("");
  const [status, setStatus] = useState("");
  const [pathPrefix, setPathPrefix] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [requestIdFilter, setRequestIdFilter] = useState("");
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const authHeader = useMemo(() => {
    if (!username || !password) return undefined;
    const token = typeof window !== "undefined" ? btoa(`${username}:${password}`) : "";
    return { Authorization: `Basic ${token}` };
  }, [username, password]);

  const fetchLogs = () =>
    startTransition(async () => {
      setError(null);
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      const params = new URLSearchParams({ limit: String(limit), offset: String(Math.max(0, offset)) });
      if (actorType.trim()) params.set("actor_type", actorType.trim());
      if (method.trim()) params.set("method", method.trim().toUpperCase());
      if (status.trim()) params.set("status_code", status.trim());
      if (pathPrefix.trim()) params.set("path_prefix", pathPrefix.trim());
      if (requestIdFilter.trim()) params.set("request_id", requestIdFilter.trim());
      if (since) {
        const date = new Date(since);
        if (!Number.isNaN(date.getTime())) params.set("since", date.toISOString());
      }
      try {
        const res = await fetch(`${API_BASE_URL}/admin/audit-logs?${params.toString()}`, { headers: authHeader });
        if (!res.ok) throw new Error(`获取失败：${res.status}`);
        const items = (await res.json()) as AuditLog[];
        setLogs(items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "获取失败");
      }
    });

  useEffect(() => {
    // Auto fetch when creds are present (dev convenience)
    if (username && password) void fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const canPrev = useMemo(() => offset > 0, [offset]);
  const canNext = useMemo(() => logs.length >= limit, [logs.length, limit]);

  const goPrev = () => {
    const next = Math.max(0, offset - limit);
    setOffset(next);
    void fetchLogs();
  };

  const goNext = () => {
    const next = offset + limit;
    setOffset(next);
    void fetchLogs();
  };

  const clearRequestId = () => {
    setRequestIdFilter("");
    setOffset(0);
    void fetchLogs();
  };

  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit-logs-${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  const exportCSV = () => {
    const headers = [
      "created_at",
      "actor_type",
      "actor_id",
      "request_id",
      "method",
      "path",
      "status_code",
      "duration_ms",
      "req_bytes",
      "res_bytes",
      "ip",
      "user_agent",
    ];
    const esc = (v: unknown) => {
      const s = String(v ?? "");
      if (s.includes(",") || s.includes("\n") || s.includes('"')) {
        return '"' + s.replace(/"/g, '""') + '"';
      }
      return s;
    };
    const rows = [headers.join(",")].concat(
      logs.map((l) =>
        [
          l.created_at,
          l.actor_type,
          l.actor_id,
          l.request_id,
          l.method,
          l.path,
          l.status_code,
          l.duration_ms ?? "",
          l.req_bytes ?? "",
          l.res_bytes ?? "",
          l.ip ?? "",
          l.user_agent ?? "",
        ]
          .map(esc)
          .join(",")
      )
    );
    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `audit-logs-${Date.now()}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  return (
    <div className="mx-auto w-full max-w-5xl space-y-8 px-4 py-12">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Admin</p>
        <h1 className="text-3xl font-semibold tracking-tight">审计日志</h1>
        <p className="text-muted-foreground">查看最近的 API 审计记录，支持按 Actor 类型与时间过滤。</p>
      </header>

      <section className="rounded-2xl border border-border bg-card/40 p-6 shadow-sm backdrop-blur">
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="username">Basic 用户名</Label>
            <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password">Basic 密码</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••" />
          </div>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-5">
          <div className="grid gap-2">
            <Label htmlFor="actor">Actor 类型</Label>
            <Input id="actor" value={actorType} onChange={(e) => setActorType(e.target.value)} placeholder="api_key / user / anonymous" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="since">时间下限</Label>
            <Input id="since" type="datetime-local" value={since} onChange={(e) => setSince(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="limit">数量</Label>
            <Input id="limit" type="number" min={1} max={200} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="method">Method</Label>
            <Input id="method" value={method} onChange={(e) => setMethod(e.target.value)} placeholder="GET/POST..." />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="status">状态码</Label>
            <Input id="status" value={status} onChange={(e) => setStatus(e.target.value)} placeholder="200" />
          </div>
        </div>
        <div className="mt-4 grid gap-4 sm:grid-cols-5">
          <div className="grid gap-2 sm:col-span-3">
            <Label htmlFor="path">Path 前缀</Label>
            <Input id="path" value={pathPrefix} onChange={(e) => setPathPrefix(e.target.value)} placeholder="/api" />
          </div>
          <div className="grid gap-2 sm:col-span-2">
            <Label>&nbsp;</Label>
            <Button type="button" onClick={() => void fetchLogs()} disabled={isPending}>
              {isPending ? "查询中…" : "查询"}
            </Button>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">记录（{logs.length}）</h2>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={exportJSON}>导出 JSON</Button>
            <Button type="button" variant="outline" size="sm" onClick={exportCSV}>导出 CSV</Button>
          </div>
        </div>
        {requestIdFilter && (
          <div className="rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-sm text-amber-700">
            已按 request_id 过滤：<code className="px-1 text-amber-800">{requestIdFilter}</code>
            <Button className="ml-3" size="sm" variant="outline" onClick={clearRequestId}>清除</Button>
          </div>
        )}
        <div className="overflow-x-auto rounded-2xl border border-border bg-card/50 shadow-sm">
          <table className="w-full min-w-max table-auto text-sm">
            <thead className="bg-muted/70 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">时间</th>
                <th className="px-4 py-3 text-left">Actor</th>
                <th className="px-4 py-3 text-left">Method</th>
                <th className="px-4 py-3 text-left">Path</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">耗时(ms)</th>
                <th className="px-4 py-3 text-left">Req/Res(Bytes)</th>
                <th className="px-4 py-3 text-left">IP</th>
                <th className="px-4 py-3 text-left">UA</th>
              </tr>
            </thead>
            <tbody>
              {logs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">暂无数据</td>
                </tr>
              ) : (
                logs.map((l, i) => (
                  <tr key={`${l.request_id}-${i}`} className="border-t border-border/60">
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(l.created_at)}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{l.actor_type}:{l.actor_id}</td>
                    <td className="px-4 py-3">{l.method}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{l.path}</td>
                    <td className="px-4 py-3">{l.status_code}</td>
                    <td className="px-4 py-3">{typeof l.duration_ms === "number" ? l.duration_ms.toFixed(1) : "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{`${l.req_bytes ?? "-"} / ${l.res_bytes ?? "-"}`}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{l.ip ?? "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground truncate max-w-[240px]">{l.user_agent ?? "-"}</td>
                    <td className="px-4 py-3">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setRequestIdFilter(l.request_id);
                          setOffset(0);
                          void fetchLogs();
                        }}
                      >
                        链路
                      </Button>
                      <Button
                        className="ml-2"
                        size="sm"
                        variant="outline"
                        onClick={() => navigator.clipboard.writeText(l.request_id)}
                      >
                        复制ID
                      </Button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm text-muted-foreground">
            偏移量 {offset}，每页 {limit}。
          </div>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={goPrev} disabled={!canPrev || isPending}>
              上一页
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={goNext} disabled={!canNext || isPending}>
              下一页
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
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
