import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-10 bg-gradient-to-b from-background via-muted/40 to-background px-6 py-16">
      <section className="max-w-3xl space-y-4 text-center">
        <p className="text-sm uppercase tracking-[0.3em] text-muted-foreground">AI Xiaohongshu</p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl lg:text-6xl">
          Craft narrative-driven commerce experiences with autonomous agents.
        </h1>
        <p className="text-lg text-muted-foreground sm:text-xl">
          Combine content strategy, channel scheduling, and performance analytics into a unified
          agentic workflow tailored for Xiaohongshu creators and brand operators.
        </p>
      </section>

      <div className="flex flex-col items-center gap-4 sm:flex-row">
        <Button asChild size="lg">
          <Link href="/docs">Explore the docs</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link href="https://github.com/yfge/ai-xiaohongshu" target="_blank" rel="noreferrer">
            View source
          </Link>
        </Button>
      </div>
    </main>
  );
}
