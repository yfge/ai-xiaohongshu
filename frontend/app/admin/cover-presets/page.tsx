"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type CoverPreset = {
  id: number;
  key: string;
  name: string;
  style_type: string;
  title_font_id?: number | null;
  subtitle_font_id?: number | null;
  safe_margin_pct?: number | null;
  padding_pct?: number | null;
  palette_start?: string | null;
  palette_end?: string | null;
  shadow?: boolean | null;
  sticker_default_text?: string | null;
  params?: Record<string, unknown> | null;
  created_at: string;
};

export default function CoverPresetsAdmin(): JSX.Element {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [items, setItems] = useState<CoverPreset[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  // create form
  const [key, setKey] = useState("gradient-red");
  const [name, setName] = useState("红橙渐变");
  const [styleType, setStyleType] = useState("gradient");
  const [paletteStart, setPaletteStart] = useState("#FF2442");
  const [paletteEnd, setPaletteEnd] = useState("#FF7A45");
  const [stickerText, setStickerText] = useState("保姆级");

  // update form
  const [editId, setEditId] = useState<number | "">("");
  const [editName, setEditName] = useState("");
  const [editSticker, setEditSticker] = useState("");

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
      try {
        const res = await fetch(`${API_BASE_URL}/admin/cover-presets`, { headers: authHeader });
        if (!res.ok) throw new Error(`获取失败：${res.status}`);
        const data = (await res.json()) as CoverPreset[];
        setItems(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : "获取失败");
      }
    });

  useEffect(() => {
    if (username && password) void fetchList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const createPreset = () =>
    startTransition(async () => {
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      setError(null);
      setInfo(null);
      try {
        const payload = {
          key: key.trim(),
          name: name.trim() || key.trim(),
          style_type: styleType.trim() || "gradient",
          palette_start: paletteStart || undefined,
          palette_end: paletteEnd || undefined,
          sticker_default_text: stickerText || undefined,
        };
        const res = await fetch(`${API_BASE_URL}/admin/cover-presets`, {
          method: "POST",
          headers: { ...authHeader, "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error(`创建失败：${res.status}`);
        setInfo("创建成功");
        void fetchList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "创建失败");
      }
    });

  const updatePreset = () =>
    startTransition(async () => {
      if (!authHeader) {
        setError("请先输入 Basic 用户名与密码");
        return;
      }
      if (!editId) {
        setError("请先输入要更新的 ID");
        return;
      }
      setError(null);
      setInfo(null);
      try {
        const res = await fetch(`${API_BASE_URL}/admin/cover-presets/${editId}`, {
          method: "PATCH",
          headers: { ...authHeader, "Content-Type": "application/json" },
          body: JSON.stringify({ name: editName || undefined, sticker_default_text: editSticker || undefined }),
        });
        if (!res.ok) throw new Error(`更新失败：${res.status}`);
        setInfo("更新成功");
        void fetchList();
      } catch (e) {
        setError(e instanceof Error ? e.message : "更新失败");
      }
    });

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">封面样式预设管理</h1>

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
        <h2 className="text-xl font-semibold">新建预设</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="key">Key</Label>
            <Input id="key" value={key} onChange={(e) => setKey(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="name">名称</Label>
            <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="styleType">样式</Label>
            <Input id="styleType" value={styleType} onChange={(e) => setStyleType(e.target.value)} placeholder="gradient|glass|sticker" />
          </div>
          <div>
            <Label htmlFor="pstart">渐变起色</Label>
            <Input id="pstart" value={paletteStart} onChange={(e) => setPaletteStart(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="pend">渐变止色</Label>
            <Input id="pend" value={paletteEnd} onChange={(e) => setPaletteEnd(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="sticker">角标文案</Label>
            <Input id="sticker" value={stickerText} onChange={(e) => setStickerText(e.target.value)} />
          </div>
        </div>
        <Button type="button" onClick={() => void createPreset()} disabled={isPending}>
          {isPending ? "处理中…" : "创建"}
        </Button>
      </section>

      <section className="rounded-xl border border-border/60 bg-card/50 p-4 shadow-sm space-y-4">
        <h2 className="text-xl font-semibold">更新预设</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <Label htmlFor="eid">ID</Label>
            <Input id="eid" value={editId} onChange={(e) => setEditId(e.target.value ? Number(e.target.value) : "")} />
          </div>
          <div>
            <Label htmlFor="ename">名称</Label>
            <Input id="ename" value={editName} onChange={(e) => setEditName(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="esticker">角标文案</Label>
            <Input id="esticker" value={editSticker} onChange={(e) => setEditSticker(e.target.value)} />
          </div>
        </div>
        <Button type="button" onClick={() => void updatePreset()} disabled={isPending}>
          {isPending ? "处理中…" : "更新"}
        </Button>
      </section>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
      )}
      {info && (
        <div className="rounded-md border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-700">{info}</div>
      )}

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">预设列表（{items.length}）</h2>
          <Button type="button" variant="outline" size="sm" onClick={() => void fetchList()} disabled={isPending}>
            {isPending ? "刷新中…" : "刷新"}
          </Button>
        </div>
        <div className="overflow-x-auto rounded-2xl border border-border bg-card/50 shadow-sm">
          <table className="w-full min-w-max table-auto text-sm">
            <thead className="bg-muted/70 text-muted-foreground">
              <tr>
                <th className="px-4 py-3 text-left">ID</th>
                <th className="px-4 py-3 text-left">Key</th>
                <th className="px-4 py-3 text-left">名称</th>
                <th className="px-4 py-3 text-left">样式</th>
                <th className="px-4 py-3 text-left">角标</th>
                <th className="px-4 py-3 text-left">时间</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center text-muted-foreground">暂无数据</td>
                </tr>
              ) : (
                items.map((p) => (
                  <tr key={p.id} className="border-t border-border/60">
                    <td className="px-4 py-3">{p.id}</td>
                    <td className="px-4 py-3">{p.key}</td>
                    <td className="px-4 py-3">{p.name}</td>
                    <td className="px-4 py-3">{p.style_type}</td>
                    <td className="px-4 py-3">{p.sticker_default_text ?? "-"}</td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(p.created_at)}</td>
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

