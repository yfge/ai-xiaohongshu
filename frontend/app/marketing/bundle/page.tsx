"use client";

import { useEffect, useMemo, useState, useTransition } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

type PromptVariant = {
  title: string;
  prompt: string;
  description?: string | null;
  hashtags?: string[];
};

type GeneratedImage = {
  prompt: PromptVariant;
  image_url?: string | null;
  image_base64?: string | null;
  size?: string | null;
};

type MarketingResponse = {
  prompts: PromptVariant[];
  images: GeneratedImage[];
};

type ResultItem = GeneratedImage & {
  previewSrc: string | null;
};

export default function MarketingBundlePage(): JSX.Element {
  const [prompt, setPrompt] = useState("");
  const [count, setCount] = useState(3);
  const [files, setFiles] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<ResultItem[]>([]);
  const [isPending, startTransition] = useTransition();

  const fileSummaries = useMemo(
    () =>
      files.map((file) => ({
        name: file.name,
        sizeLabel: formatBytes(file.size),
        type: file.type || "image",
      })),
    [files],
  );

  useEffect(() => {
    if (!files.length) {
      setResults([]);
    }
  }, [files]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(event.target.files ?? []);
    setFiles(selectedFiles);
  };

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!files.length) {
      setError("请至少上传一张参考图");
      return;
    }

    startTransition(async () => {
      setError(null);
      setResults([]);

      const formData = new FormData();
      formData.append("prompt", prompt.trim());
      formData.append("count", count.toString());
      files.forEach((file) => {
        formData.append("images", file);
      });

      try {
        const response = await fetch(`${API_BASE_URL}/marketing/collage`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const detail = await safeParseError(response);
          throw new Error(detail ?? "生成失败，请稍后重试");
        }

        const payload = (await response.json()) as MarketingResponse;
        const nextResults = payload.images.map((item) => ({
          ...item,
          previewSrc: resolvePreviewSource(item),
        }));
        setResults(nextResults);
      } catch (err) {
        setError(err instanceof Error ? err.message : "生成失败，请稍后再试");
      }
    });
  };

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-10 px-4 py-12">
      <header className="space-y-2 text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">营销工具</p>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          小红书种草营销组图助理
        </h1>
        <p className="text-muted-foreground">
          上传品牌素材与创意简报，批量生成多风格提示词与图像，辅助快速出图与主题策划。
        </p>
      </header>

      <form
        onSubmit={handleSubmit}
        className="grid gap-6 rounded-2xl border border-border bg-card/40 p-6 shadow-sm backdrop-blur-sm"
      >
        <div className="grid gap-2">
          <Label htmlFor="prompt">创意提示词</Label>
          <Textarea
            id="prompt"
            rows={4}
            placeholder="例如：秋冬氛围感穿搭，突出产品温暖质感"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            required
          />
          <p className="text-sm text-muted-foreground">
            描述核心卖点、场景氛围或必须出现的元素，系统会结合参考图生成多个提示词。
          </p>
        </div>

        <div className="grid gap-2">
          <Label htmlFor="images">参考图片</Label>
          <Input id="images" name="images" type="file" accept="image/*" multiple onChange={handleFileChange} />
          <p className="text-sm text-muted-foreground">
            支持一次上传多张图片（建议小于 5MB），生成时会统一作为视觉参考。
          </p>
          {!!fileSummaries.length && (
            <ul className="grid gap-1 rounded-md border border-dashed border-muted-foreground/40 bg-muted/40 p-3 text-sm">
              {fileSummaries.map((file) => (
                <li key={`${file.name}-${file.sizeLabel}`} className="flex items-center justify-between">
                  <span className="font-medium text-foreground">{file.name}</span>
                  <span className="text-muted-foreground">{file.sizeLabel}</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="grid w-full gap-2 sm:max-w-xs">
          <Label htmlFor="count">生成数量</Label>
          <Input
            id="count"
            name="count"
            type="number"
            min={1}
            max={6}
            value={count}
            onChange={(event) => setCount(Number(event.target.value))}
            required
          />
          <p className="text-sm text-muted-foreground">一次最多生成 6 组提示词及图像。</p>
        </div>

        {error && (
          <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        )}

        <div className="flex flex-wrap items-center gap-4">
          <Button type="submit" size="lg" disabled={isPending || !prompt.trim() || !files.length}>
            {isPending ? "生成中…" : "生成组图"}
          </Button>
          <span className="text-sm text-muted-foreground">
            将调用火山引擎 Ark 模型生成 {count} 组提示词与图像。
          </span>
        </div>
      </form>

      {!!results.length && (
        <section className="space-y-4">
          <h2 className="text-2xl font-semibold">生成结果</h2>
          <div className="grid gap-6 md:grid-cols-2">
            {results.map((item, index) => (
              <article
                key={`${item.prompt.title}-${index}`}
                className="flex flex-col gap-4 rounded-2xl border border-border bg-card/60 p-4 shadow-sm"
              >
                {item.previewSrc ? (
                  <img
                    src={item.previewSrc}
                    alt={item.prompt.title}
                    className="h-56 w-full rounded-xl object-cover"
                  />
                ) : (
                  <div className="flex h-56 w-full items-center justify-center rounded-xl border border-dashed text-sm text-muted-foreground">
                    图像生成中/无预览
                  </div>
                )}
                <div className="space-y-2">
                  <div>
                    <p className="text-sm uppercase tracking-wide text-muted-foreground">主题</p>
                    <h3 className="text-xl font-semibold">{item.prompt.title}</h3>
                  </div>
                  {item.prompt.description && (
                    <p className="text-sm text-muted-foreground leading-relaxed">
                      {item.prompt.description}
                    </p>
                  )}
                  <div>
                    <p className="text-sm uppercase tracking-wide text-muted-foreground">Prompt</p>
                    <pre className="overflow-x-auto whitespace-pre-wrap rounded-md bg-muted/60 p-3 text-xs text-foreground">
                      {item.prompt.prompt}
                    </pre>
                  </div>
                  {!!item.prompt.hashtags?.length && (
                    <div className="flex flex-wrap gap-2">
                      {item.prompt.hashtags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground"
                        >
                          #{tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function resolvePreviewSource(item: GeneratedImage): string | null {
  if (item.image_base64) {
    return `data:image/png;base64,${item.image_base64}`;
  }
  if (item.image_url) {
    return item.image_url;
  }
  return null;
}

async function safeParseError(response: Response): Promise<string | null> {
  try {
    const data = (await response.json()) as { detail?: string };
    return data.detail ?? null;
  } catch (error) {
    console.warn("Failed to parse error message", error);
    return null;
  }
}

function formatBytes(value: number): string {
  if (value === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"] as const;
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const size = value / Math.pow(1024, index);
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}
