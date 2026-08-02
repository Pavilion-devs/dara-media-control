"use client";

import { AudioLines, Images } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { Badge, EmptyState } from "@/components/ui";

import { liveRunListSchema, type LiveRun } from "../../run-schema";
import { projectListSchema } from "../../project-schema";

function AssetPreview({ run }: { run: LiveRun }) {
  if (run.pipeline_id === "motion-spot") {
    return (
      <video
        aria-label={`Generated motion asset for ${run.project_id}`}
        className="aspect-[4/3] w-full bg-inset object-cover"
        muted
        playsInline
        preload="metadata"
        src={run.asset_url as string}
      />
    );
  }
  if (run.pipeline_id === "voiceover-pack") {
    return (
      <div className="flex aspect-[4/3] w-full items-center justify-center bg-inset">
        <AudioLines aria-hidden className="size-10 text-faint" strokeWidth={1.5} />
        <span className="sr-only">Generated audio asset for {run.project_id}</span>
      </div>
    );
  }
  return (
    <img
      alt={`Generated image asset for ${run.project_id}`}
      className="aspect-[4/3] w-full bg-inset object-cover"
      src={run.asset_url as string}
    />
  );
}

export function AssetsScreen() {
  const [runs, setRuns] = useState<LiveRun[]>([]);
  const [state, setState] = useState<"loading" | "live" | "unavailable">("loading");

  useEffect(() => {
    const controller = new AbortController();
    void Promise.all([
      fetch("/api/runs?limit=100", { cache: "no-store", signal: controller.signal }),
      fetch("/api/projects", { cache: "no-store", signal: controller.signal }),
    ])
      .then(async ([runResponse, projectResponse]) => {
        if (!runResponse.ok || !projectResponse.ok) {
          throw new Error("Asset history unavailable");
        }
        const parsed = liveRunListSchema.parse(await runResponse.json());
        const projects = projectListSchema.parse(await projectResponse.json());
        const projectIds = projects.items.map((project) => project.project_id);
        setRuns(
          parsed.items.filter(
            (run) =>
              projectIds.includes(run.project_id)
              && run.status === "succeeded"
              && run.asset_id
              && run.asset_url,
          ),
        );
        setState("live");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setState("unavailable");
      });
    return () => controller.abort();
  }, []);

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
            Published assets
          </p>
          <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
            The delivered work.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            Every item here is a live B2 asset produced by a completed Dara run.
            Open one to inspect its hashes, manifest, cost, and lineage.
          </p>
        </div>
        <Badge dot tone={state === "live" ? "allow" : "warn"}>
          {state === "live"
            ? `${runs.length} published asset${runs.length === 1 ? "" : "s"}`
            : state === "loading"
              ? "Reading B2 records"
              : "Live assets unavailable"}
        </Badge>
      </div>

      {state === "live" && runs.length ? (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {runs.map((run) => (
            <Link
              className="group overflow-hidden rounded-2xl border border-line bg-surface transition-colors hover:border-accent/40"
              href={`/assets/${encodeURIComponent(run.asset_id as string)}`}
              key={run.asset_id}
            >
              <AssetPreview run={run} />
              <div className="grid gap-2 p-4">
                <p className="line-clamp-2 text-sm font-semibold text-ink">
                  {run.prompt}
                </p>
                <p className="truncate font-mono text-[11px] text-subtle">
                  {run.project_id} · {run.asset_id}
                </p>
                <span className="flex items-center justify-between gap-3">
                  <Badge dot tone="allow">Published</Badge>
                  <span className="font-mono text-xs text-subtle">
                    ${run.actual_cost_usd ?? "unknown"}
                  </span>
                </span>
              </div>
            </Link>
          ))}
        </div>
      ) : state === "live" ? (
        <EmptyState
          description="Complete a generation in Studio and its published asset will appear here."
          icon={Images}
          title="No published assets yet"
        />
      ) : state === "unavailable" ? (
        <EmptyState
          description="Dara could not read the live B2 run store. No sample gallery has been substituted."
          icon={Images}
          title="Assets unavailable"
        />
      ) : (
        <div className="min-h-48 animate-pulse rounded-2xl border border-line bg-surface" />
      )}
    </div>
  );
}
