"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type ApiKey = {
  id: string;
  name: string;
  prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at: string;
  last_used_at?: string | null;
};

export default function ApiKeysAdmin(): JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [name, setName] = useState("ci-client");
  const [scopes, setScopes] = useState("marketing:collage");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [plaintext, setPlaintext] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const authHeader = useMemo(() => {
    if (!username || !password) return undefined;
    const token = typeof window !== "undefined" ? btoa(`${username}:${password}`) : "";
    return { Authorization: `Basic ${token}` };
  }, [username, password]);

  const fetchList = () =>
    startTransition(async () => {
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      setError(null);
      setInfo(null);
      setPlaintext(null);
      try {
        const res = await fetch(`${API_BASE_URL}/admin/api-keys`, { headers: authHeader });
        if (!res.ok) throw new Error(`获取失败：${res.status}`);
        const items = (await res.json()) as ApiKey[];
        setKeys(items);
      } catch (e) {
        setError(e instanceof Error ? e.message : "获取失败");
      }
    });

  useEffect(() => {
    // lazy initial fetch only if creds provided (dev convenience)
    if (username && password) void fetchList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createKey = () =>
    startTransition(async () => {
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      setError(null);
      setInfo(null);
      setPlaintext(null);
      try {
        const res = await fetch(`${API_BASE_URL}/admin/api-keys`, {
          method: "POST",
          headers: { ...authHeader, "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() || "client", scopes: scopes.split(/[,\s]+/).filter(Boolean) }),
        });
        if (!res.ok) throw new Error(`创建失败：${res.status}`);
        const payload = (await res.json()) as { api_key: string } & ApiKey;
        setPlaintext(payload.api_key);
        setInfo("创建成功，请立即复制明文 API Key（仅显示一次）");
        void fetchList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "创建失败");
      }
    });

  const toggleActive = (id: string, isActive: boolean) =>
    startTransition(async () => {
      if (!authHeader) return;
      try {
        const res = await fetch(`${API_BASE_URL}/admin/api-keys/${id}`, {
          method: "PATCH",
          headers: { ...authHeader, "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: !isActive }),
        });
        if (!res.ok) throw new Error("更新失败");
        void fetchList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "更新失败");
      }
    });

  return (
    <div className="mx-auto w-full max-w-4xl space-y-8 px-4 py-12">
      <header className="space-y-2">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">Admin</p>
        <h1 className="text-3xl font-semibold tracking-tight">API Key 管理</h1>
        <p className="text-muted-foreground">使用 Basic 认证访问管理接口。请勿在生产环境将密码硬编码到前端。</p>
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
        <div className="mt-4 flex items-center gap-3">
          <Button type="button" onClick={() => void fetchList()} disabled={isPending}>
            {isPending ? "加载中…" : "刷新列表"}
          </Button>
        </div>
      </section>

      <section className="rounded-2xl border border-border bg-card/40 p-6 shadow-sm backdrop-blur">
        <h2 className="mb-3 text-xl font-semibold">创建新 Key</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="name">名称</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} placeholder="ci-client" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="scopes">Scopes（逗号或空格分隔）</Label>
            <Input id="scopes" value={scopes} onChange={(e) => setScopes(e.target.value)} placeholder="marketing:collage" />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <Button type="button" onClick={() => void createKey()} disabled={isPending}>
            {isPending ? "创建中…" : "创建 API Key"}
          </Button>
          {plaintext && (
            <span className="truncate text-sm text-amber-600">明文 Key：{plaintext}</span>
          )}
        </div>
      </section>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
      )}
      {info && (
        <div className="rounded-md border border-amber-400/40 bg-amber-400/10 px-3 py-2 text-sm text-amber-700">{info}</div>
      )}

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Key 列表（{keys.length}）</h2>
        <div className="overflow-x-auto rounded-2xl border border-border bg-card/50 shadow-sm">
          <table className="w-full min-w-max table-auto text-sm">
            <thead className="bg-muted/70 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">名称</th>
                <th className="px-4 py-3 text-left">前缀</th>
                <th className="px-4 py-3 text-left">Scopes</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">最近使用</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody>
              {keys.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">暂无数据</td>
                </tr>
              ) : (
                keys.map((k) => (
                  <tr key={k.id} className="border-t border-border/60">
                    <td className="px-4 py-3 font-medium text-foreground">{k.name}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{k.prefix}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{k.scopes.join(", ")}</td>
                    <td className="px-4 py-3">{k.is_active ? "active" : "disabled"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{k.last_used_at ? new Date(k.last_used_at).toLocaleString() : "-"}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="outline" onClick={() => void toggleActive(k.id, k.is_active)} disabled={isPending}>
                        {k.is_active ? "禁用" : "启用"}
                      </Button>
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

