"use client";

import { useState, useTransition } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type CoverImage = {
  size: "1080x1920" | "1080x1440";
  image_base64: string;
};

type CoverResult = {
  request_id: string;
  style: string;
  title: string;
  subtitle?: string | null;
  images: CoverImage[];
};

export default function CreativeCoversPage(): JSX.Element {
  const [video, setVideo] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [style, setStyle] = useState("gradient");
  const [sticker, setSticker] = useState("");
  const [presetKey, setPresetKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CoverResult | null>(null);
  const [isPending, startTransition] = useTransition();

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setVideo(f);
  };

  const onSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!video) {
      setError("请先选择视频文件");
      return;
    }
    startTransition(async () => {
      setError(null);
      setResult(null);
      try {
        const fd = new FormData();
        fd.append("title", title.trim());
        if (subtitle.trim()) fd.append("subtitle", subtitle.trim());
        fd.append("style", style);
        if (sticker.trim()) fd.append("sticker", sticker.trim());
        if (presetKey.trim()) fd.append("preset_key", presetKey.trim());
        fd.append("video", video);
        const res = await fetch(`${API_BASE_URL}/creative/covers`, { method: "POST", body: fd });
        if (!res.ok) {
          const detail = await safeParseError(res);
          throw new Error(formatErrorMessage(res.status, detail));
        }
        const payload = (await res.json()) as CoverResult;
        setResult(payload);
      } catch (err) {
        setError(err instanceof Error ? err.message : "生成失败，请稍后再试");
      }
    });
  };

  const src = (img?: CoverImage) => (img ? `data:image/jpeg;base64,${img.image_base64}` : "");

  return (
    <div className="mx-auto max-w-5xl space-y-8 p-6">
      <header className="space-y-2 text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">创作工具</p>
        <h1 className="text-3xl font-semibold">RED 自动封面生成（CPU）</h1>
        <p className="text-muted-foreground">上传视频与标题，生成 9:16 与 3:4 两份封面预览。可选样式或预设 Key。</p>
      </header>

      <form onSubmit={onSubmit} className="grid gap-6 rounded-2xl border border-border bg-card/40 p-6 shadow-sm">
        <div className="grid gap-2">
          <Label htmlFor="video">视频文件</Label>
          <Input id="video" type="file" accept="video/*" onChange={onFileChange} />
          {video && (
            <p className="text-sm text-muted-foreground">{video.name}（{formatBytes(video.size)}）</p>
          )}
        </div>

        <div className="grid gap-2">
          <Label htmlFor="title">标题</Label>
          <Input id="title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例如：租房党厨房收纳：3㎡立刻清爽" required />
          <p className="text-sm text-muted-foreground">建议 10–18 个中文；超长将自动换行。</p>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="subtitle">副标题（可选）</Label>
          <Input id="subtitle" value={subtitle} onChange={(e) => setSubtitle(e.target.value)} placeholder="例如：10个挂杆 + 4个抽屉分隔，成本<50元" />
        </div>

        <div className="grid gap-3 sm:grid-cols-3">
          <div className="grid gap-2">
            <Label htmlFor="style">样式</Label>
            <select id="style" className="h-9 rounded-md border bg-background px-3" value={style} onChange={(e) => setStyle(e.target.value)}>
              <option value="gradient">gradient（红橙渐变）</option>
              <option value="glass">glass（半透明底板）</option>
              <option value="sticker">sticker（角标贴纸）</option>
            </select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="sticker">角标文案（可选）</Label>
            <Input id="sticker" value={sticker} onChange={(e) => setSticker(e.target.value)} placeholder="如：保姆级 / 避坑" />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="presetKey">预设 Key（可选）</Label>
            <Input id="presetKey" value={presetKey} onChange={(e) => setPresetKey(e.target.value)} placeholder="如：gradient-red（需后台已创建）" />
            <p className="text-xs text-muted-foreground">填写后优先使用预设；否则使用上方样式。</p>
          </div>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
        )}

        <div className="flex items-center gap-3">
          <Button type="submit" size="lg" disabled={isPending || !title.trim() || !video}>
            {isPending ? "生成中…" : "生成封面"}
          </Button>
          <p className="text-sm text-muted-foreground">返回 Base64 预览图，可直接下载或用于比对。</p>
        </div>
      </form>

      {result && (
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold">生成结果</h2>
          <div className="grid gap-6 md:grid-cols-2">
            <article className="space-y-3 rounded-2xl border border-border bg-card/60 p-4 shadow-sm">
              <h3 className="text-sm font-medium text-muted-foreground">1080×1920（9:16）</h3>
              <img src={src(result.images.find((i) => i.size === "1080x1920"))} alt="9:16" className="h-96 w-full rounded-xl object-cover" />
              <Button
                variant="outline"
                onClick={() => downloadBase64(src(result.images.find((i) => i.size === "1080x1920")), `cover_${result.request_id}_1080x1920.jpg`)}
              >
                下载 9:16
              </Button>
            </article>
            <article className="space-y-3 rounded-2xl border border-border bg-card/60 p-4 shadow-sm">
              <h3 className="text-sm font-medium text-muted-foreground">1080×1440（3:4）</h3>
              <img src={src(result.images.find((i) => i.size === "1080x1440"))} alt="3:4" className="h-96 w-full rounded-xl object-cover" />
              <Button
                variant="outline"
                onClick={() => downloadBase64(src(result.images.find((i) => i.size === "1080x1440")), `cover_${result.request_id}_1080x1440.jpg`)}
              >
                下载 3:4
              </Button>
            </article>
          </div>
        </section>
      )}
    </div>
  );
}

function downloadBase64(dataUrl: string, filename: string): void {
  try {
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  } catch {
    // noop
  }
}

async function safeParseError(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? null;
  } catch {
    return null;
  }
}

function formatErrorMessage(status: number, detail: string | null): string {
  if (status === 503) return detail ?? "生成依赖未安装（Pillow/OpenCV）";
  if (status >= 500) return detail ?? "服务暂不可用，请稍后再试";
  if (status === 400) return detail ?? "参数错误";
  return detail ?? "请求失败";
}

function formatBytes(value: number): string {
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"] as const;
  const idx = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const size = value / Math.pow(1024, idx);
  return `${size.toFixed(size >= 10 || idx === 0 ? 0 : 1)} ${units[idx]}`;
}

