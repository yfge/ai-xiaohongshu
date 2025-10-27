"use client";

import { useMemo, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type CoverJob = {
  id: number;
  request_id: string;
  actor_type: string;
  actor_id: string;
  title: string;
  subtitle?: string | null;
  style_key?: string | null;
  preset_id?: number | null;
  status: string;
  duration_ms?: number | null;
  result_9x16_url?: string | null;
  result_3x4_url?: string | null;
  created_at: string;
};

export default function CoverJobsAdmin(): JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [jobs, setJobs] = useState<CoverJob[]>([]);
  const [status, setStatus] = useState("");
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const authHeader = useMemo(() => {
    if (!username || !password) return undefined;
    const token = typeof window !== "undefined" ? btoa(`${username}:${password}`) : "";
    return { Authorization: `Basic ${token}` };
  }, [username, password]);

  const fetchJobs = () =>
    startTransition(async () => {
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      setError(null);
      const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
      if (status) params.set("status", status);
      try {
        const res = await fetch(`${API_BASE_URL}/admin/cover-jobs?${params.toString()}`, { headers: authHeader });
        if (!res.ok) throw new Error(`获取失败：${res.status}`);
        const items = (await res.json()) as CoverJob[];
        setJobs(items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "获取失败");
      }
    });

  const goPrev = () => setOffset((o) => Math.max(0, o - limit));
  const goNext = () => setOffset((o) => o + limit);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">封面任务列表</h1>

      <section className="rounded-xl border border-border/60 bg-card/50 p-4 shadow-sm">
        <p className="text-muted-foreground">使用 Basic 认证访问管理接口。请勿在生产环境将密码硬编码到前端。</p>
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="username">Basic 用户名</Label>
            <Input id="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="admin" />
          </div>
          <div>
            <Label htmlFor="password">Basic 密码</Label>
            <Input id="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="secret" />
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-border/60 bg-card/50 p-4 shadow-sm space-y-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <div>
            <Label htmlFor="status">状态</Label>
            <Input id="status" value={status} onChange={(e) => setStatus(e.target.value)} placeholder="succeeded|failed|running" />
          </div>
          <div>
            <Label htmlFor="limit">每页</Label>
            <Input id="limit" type="number" value={limit} onChange={(e) => setLimit(Number(e.target.value) || 50)} />
          </div>
          <div>
            <Label htmlFor="offset">偏移</Label>
            <Input id="offset" type="number" value={offset} onChange={(e) => setOffset(Number(e.target.value) || 0)} />
          </div>
          <div className="flex items-end">
            <Button type="button" onClick={() => void fetchJobs()} disabled={isPending}>
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
          <h2 className="text-xl font-semibold">记录（{jobs.length}）</h2>
          <div className="flex items-center gap-2">
            <Button type="button" variant="outline" size="sm" onClick={goPrev} disabled={isPending || offset <= 0}>
              上一页
            </Button>
            <Button type="button" variant="outline" size="sm" onClick={goNext} disabled={isPending}>
              下一页
            </Button>
          </div>
        </div>
        <div className="overflow-x-auto rounded-2xl border border-border bg-card/50 shadow-sm">
          <table className="w-full min-w-max table-auto text-sm">
            <thead className="bg-muted/70 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">时间</th>
                <th className="px-4 py-3 text-left">RequestID</th>
                <th className="px-4 py-3 text-left">标题</th>
                <th className="px-4 py-3 text-left">样式/预设</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">耗时(ms)</th>
                <th className="px-4 py-3 text-left">结果</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">暂无数据</td>
                </tr>
              ) : (
                jobs.map((j) => (
                  <tr key={j.id} className="border-t border-border/60">
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(j.created_at)}</td>
                    <td className="px-4 py-3 text-xs">{j.request_id}</td>
                    <td className="px-4 py-3">{j.title}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{j.style_key ?? "-"} / {j.preset_id ?? "-"}</td>
                    <td className="px-4 py-3">{j.status}</td>
                    <td className="px-4 py-3">{typeof j.duration_ms === "number" ? j.duration_ms.toFixed(1) : "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground truncate max-w-[240px]">
                      {(j.result_9x16_url ?? "-") + " | " + (j.result_3x4_url ?? "-")}
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

function formatDate(value: string): string {
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  } catch {
    return value;
  }
}

