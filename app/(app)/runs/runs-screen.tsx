"use client";

import {
  AudioLines,
  ChevronRight,
  Clapperboard,
  ImageIcon,
  ListOrdered,
  RotateCcw,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { EventStream, type RunEvent } from "@/components/dara/event-stream";
import { derivePhases } from "@/components/dara/run-phases";
import { ShareAction } from "@/components/dara/share-action";
import { RegenerationAction } from "@/components/dara/regeneration-action";
import { VersionTree } from "@/components/dara/version-tree";
import {
  Badge,
  Button,
  EmptyState,
  Panel,
  Stepper,
  cn,
  type Tone,
} from "@/components/ui";

import demoSeedData from "../../../api/seeds/demo-runs.json";
import { demoSeedCorpusSchema, type DemoSeedRun } from "../../demo-seed-schema";
import {
  liveRunListSchema,
  type LiveRun,
} from "../../run-schema";

const corpus = demoSeedCorpusSchema.parse(demoSeedData);

const pipelineIcon: Record<string, typeof ImageIcon> = {
  "still-campaign": ImageIcon,
  regenerate: RotateCcw,
  "motion-spot": Clapperboard,
  "voiceover-pack": AudioLines,
};

const outcomeTone: Record<DemoSeedRun["outcome"], Tone> = {
  succeeded: "allow",
  blocked: "block",
  failed: "warn",
};

function toRunEvents(run: DemoSeedRun): RunEvent[] {
  return run.events.map((event, index) => ({
    seq: index + 1,
    time: `${(event.at_ms / 1000).toFixed(2)}s`,
    provider: event.provider,
    model: event.model,
    message: event.message,
    kind: event.type,
    tone:
      event.type === "step.failover"
        ? "failover"
        : event.type === "qa.revised"
          ? "revised"
          : event.type === "run.completed"
              || event.type === "publish.completed"
              || (event.type === "agent.iteration.evaluated"
                && event.message.includes("passed"))
            ? "success"
            : "normal",
  }));
}

function toLiveRunEvents(run: LiveRun): RunEvent[] {
  return run.events.map((event) => ({
    seq: event.seq,
    time: new Date(event.at).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "UTC",
    }),
    provider: event.provider ?? "dara",
    model: event.model ?? "control-plane",
    message: event.message,
    kind: event.type,
    tone:
      event.type === "step.failover"
        ? "failover"
        : event.type === "qa.revised"
          ? "revised"
          : event.type === "run.completed"
              || event.type === "publish.completed"
            ? "success"
            : "normal",
  }));
}

function Filter<T extends string>({
  label,
  onChange,
  options,
  value,
}: {
  label: string;
  onChange: (next: T) => void;
  options: Array<{ value: T; label: string }>;
  value: T;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
        {label}
      </span>
      {options.map((option) => (
        <button
          aria-pressed={value === option.value}
          className={cn(
            "rounded-full border px-3 py-1 text-xs font-medium transition-colors",
            value === option.value
              ? "border-accent/40 bg-accent/10 text-accent-ink"
              : "border-line text-subtle hover:bg-inset hover:text-ink",
          )}
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function RunRow({ run }: { run: DemoSeedRun }) {
  const [open, setOpen] = useState(false);
  const Icon = pipelineIcon[run.pipeline_id] ?? ImageIcon;
  const events = useMemo(() => toRunEvents(run), [run]);
  const phases = derivePhases(
    events.map((event) => event.kind),
    false,
  );

  return (
    <div className="border-b border-line last:border-0">
      <button
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-inset"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <Icon aria-hidden className="size-4 shrink-0 text-subtle" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {run.title}
          </span>
          <span className="mt-0.5 block truncate font-mono text-[11px] text-subtle">
            {run.provider} · {run.model} · {run.policy_id}
          </span>
        </span>
        <span className="hidden shrink-0 text-right sm:block">
          <span className="block font-mono text-xs text-ink">
            {run.qa_score == null
              ? "QA —"
              : `QA ${Math.round(run.qa_score * 100)}`}
          </span>
          <span className="mt-0.5 block font-mono text-[11px] text-subtle">
            ${run.cost_usd}
          </span>
        </span>
        {/* Never let a fixture read as a paid production call. */}
        <Badge tone={run.evidence === "production-proof" ? "accent" : "neutral"}>
          {run.evidence === "production-proof" ? "Proof" : "Fixture"}
        </Badge>
        <Badge dot tone={outcomeTone[run.outcome]}>
          {run.outcome}
        </Badge>
        <ChevronRight
          aria-hidden
          className={cn(
            "size-4 shrink-0 text-faint transition-transform",
            open && "rotate-90",
          )}
        />
      </button>

      {open ? (
        <div className="grid gap-5 border-t border-line bg-inset/40 px-5 py-5">
          <p className="text-sm leading-relaxed text-muted">{run.brief}</p>
          <Stepper steps={phases} />
          {run.asset_url ? (
            // Fixture assets are committed files; live assets are signed by B2.
            <img
              alt={`Asset produced by ${run.title}`}
              className="max-w-sm rounded-xl border border-line bg-surface object-cover"
              src={run.asset_url}
            />
          ) : null}
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
            {[
              { label: "Project", value: run.project_id },
              { label: "Attempts", value: String(run.qa_attempts) },
              { label: "Cost", value: `$${run.cost_usd}` },
              { label: "Prevented", value: `$${run.saved_cost_usd}` },
            ].map((item) => (
              <div className="grid gap-1 bg-surface px-4 py-3" key={item.label}>
                <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  {item.label}
                </dt>
                <dd className="truncate font-mono text-sm text-ink">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
          <EventStream events={events} />
        </div>
      ) : null}
    </div>
  );
}

const liveStatusTone: Record<LiveRun["status"], Tone> = {
  queued: "warn",
  running: "warn",
  publishing: "warn",
  succeeded: "allow",
  failed: "block",
  blocked: "block",
  cancelled: "neutral",
};

function LiveRunRow({
  relatedRun,
  run,
}: {
  relatedRun?: LiveRun;
  run: LiveRun;
}) {
  const [open, setOpen] = useState(false);
  const events = useMemo(() => toLiveRunEvents(run), [run]);
  const phases = derivePhases(
    events.map((event) => event.kind),
    ["queued", "running", "publishing"].includes(run.status),
  );

  return (
    <div className="border-b border-line last:border-0">
      <button
        aria-expanded={open}
        className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-inset"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <ImageIcon aria-hidden className="size-4 shrink-0 text-subtle" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-ink">
            {run.prompt}
          </span>
          <span className="mt-0.5 block truncate font-mono text-[11px] text-subtle">
            {run.project_id} · {run.policy_id} · {run.job_id}
          </span>
        </span>
        <span className="hidden shrink-0 text-right sm:block">
          <span className="block font-mono text-xs text-ink">
            {run.qa_score == null
              ? "QA —"
              : `QA ${Math.round(run.qa_score * 100)}`}
          </span>
          <span className="mt-0.5 block font-mono text-[11px] text-subtle">
            ${run.actual_cost_usd ?? run.expected_cost_usd}
          </span>
        </span>
        <Badge dot tone={liveStatusTone[run.status]}>
          {run.status}
        </Badge>
        <ChevronRight
          aria-hidden
          className={cn(
            "size-4 shrink-0 text-faint transition-transform",
            open && "rotate-90",
          )}
        />
      </button>
      {open ? (
        <div className="grid gap-5 border-t border-line bg-inset/40 px-5 py-5">
          <Stepper steps={phases} />
          {run.asset_url ? (
            <img
              alt={`Live output for ${run.project_id}`}
              className="max-w-sm rounded-xl border border-line bg-surface object-cover"
              src={run.asset_url}
            />
          ) : null}
          <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
            {[
              { label: "Created", value: new Date(run.created_at).toLocaleString("en-GB") },
              { label: "Attempts", value: String(run.qa_attempts) },
              { label: "Expected", value: `$${run.expected_cost_usd}` },
              {
                label: "Actual",
                value: run.actual_cost_usd ? `$${run.actual_cost_usd}` : "—",
              },
            ].map((item) => (
              <div className="grid gap-1 bg-surface px-4 py-3" key={item.label}>
                <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  {item.label}
                </dt>
                <dd className="truncate font-mono text-sm text-ink">
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>
          <EventStream events={events} />
          {run.attempts.length ? (
            <div>
              <p className="mb-3 text-sm font-semibold text-ink">Version tree</p>
              <VersionTree
                nodes={run.attempts.map((attempt) => ({
                  id: attempt.genblaze_run_id,
                  parentId: attempt.parent_run_id,
                  status: attempt.status,
                  label: `Attempt ${attempt.attempt}`,
                  prompt: attempt.prompt,
                  provider: attempt.provider,
                  model: attempt.model,
                  qaScore: attempt.qa_score,
                }))}
              />
            </div>
          ) : null}
          {run.status === "succeeded" && run.asset_id ? (
            <>
              <RegenerationAction relatedRun={relatedRun} run={run} />
              <ShareAction assetId={run.asset_id} jobId={run.job_id} />
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function RunsScreen() {
  const [pipeline, setPipeline] = useState<string>("all");
  const [outcome, setOutcome] = useState<string>("all");
  const [liveRuns, setLiveRuns] = useState<LiveRun[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [liveState, setLiveState] = useState<
    "loading" | "live" | "unavailable"
  >("loading");

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/runs?limit=50", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) throw new Error("Live run history is unavailable.");
        const parsed = liveRunListSchema.parse(await response.json());
        setLiveRuns(parsed.items);
        setNextCursor(parsed.next_cursor);
        setLiveState("live");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLiveState("unavailable");
      });
    return () => controller.abort();
  }, []);

  async function loadMoreLiveRuns() {
    if (!nextCursor || loadingMore) return;
    setLoadingMore(true);
    try {
      const response = await fetch(
        `/api/runs?limit=50&cursor=${encodeURIComponent(nextCursor)}`,
        { cache: "no-store" },
      );
      if (!response.ok) throw new Error("Live run history is unavailable.");
      const parsed = liveRunListSchema.parse(await response.json());
      setLiveRuns((current) => [...current, ...parsed.items]);
      setNextCursor(parsed.next_cursor);
    } catch {
      setNextCursor(null);
    } finally {
      setLoadingMore(false);
    }
  }

  const runs = corpus.runs.filter(
    (run) =>
      (pipeline === "all" || run.pipeline_id === pipeline)
      && (outcome === "all" || run.outcome === outcome),
  );

  // Totals are derived from the corpus, never hardcoded.
  const totals = {
    all: corpus.runs.length,
    approved: corpus.runs.filter((run) => run.approved).length,
    blocked: corpus.runs.filter((run) => run.outcome === "blocked").length,
    failed: corpus.runs.filter((run) => run.outcome === "failed").length,
    prevented: corpus.runs
      .reduce((sum, run) => sum + Number(run.saved_cost_usd), 0)
      .toFixed(6),
    proofs: corpus.runs.filter((run) => run.evidence === "production-proof")
      .length,
  };

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
            Run history
          </p>
          <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
            Every attempt, kept.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            Failed, rejected, and policy-blocked work stays visible. A sanitised
            history would not be a record.
          </p>
        </div>
        <Badge dot tone={liveState === "live" ? "allow" : "warn"}>
          {liveState === "live"
            ? `${liveRuns.length} live run${liveRuns.length === 1 ? "" : "s"}`
            : liveState === "loading"
              ? "Checking live history"
              : "Committed corpus available"}
        </Badge>
      </div>

      {liveState === "live" ? (
        <section className="grid gap-3" aria-labelledby="live-run-history">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-ink" id="live-run-history">
                Live B2 history
              </h2>
              <p className="mt-1 text-xs text-subtle">
                Durable run records returned by the active Dara API.
              </p>
            </div>
            <Badge dot tone="allow">Live</Badge>
          </div>
          {liveRuns.length ? (
            <>
              <Panel>
                {liveRuns.map((run) => (
                  <LiveRunRow
                    key={run.job_id}
                    relatedRun={liveRuns.find(
                      (candidate) =>
                        candidate.parent_job_id === run.job_id
                        || run.parent_job_id === candidate.job_id,
                    )}
                    run={run}
                  />
                ))}
              </Panel>
              {nextCursor ? (
                <Button
                  disabled={loadingMore}
                  onClick={() => void loadMoreLiveRuns()}
                  size="sm"
                  variant="secondary"
                >
                  {loadingMore ? "Loading…" : "Load older runs"}
                </Button>
              ) : null}
            </>
          ) : (
            <EmptyState
              description="Start a live run in Studio and it will appear here."
              icon={ListOrdered}
              title="No live runs yet"
            />
          )}
        </section>
      ) : null}

      <div>
        <h2 className="text-lg font-semibold text-ink">Committed evidence corpus</h2>
        <p className="mt-1 text-xs text-subtle">
          Production proofs and deterministic fixtures retained for the zero-spend tour.
        </p>
      </div>

      <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-2xl border border-line bg-line md:grid-cols-5">
        {[
          { label: "Runs", value: String(totals.all) },
          { label: "Approved", value: String(totals.approved) },
          { label: "Blocked", value: String(totals.blocked) },
          { label: "Failed", value: String(totals.failed) },
          { label: "Spend prevented", value: `$${totals.prevented}` },
        ].map((item) => (
          <div className="grid gap-1 bg-surface px-4 py-4" key={item.label}>
            <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
              {item.label}
            </dt>
            <dd className="font-mono text-xl text-ink">{item.value}</dd>
          </div>
        ))}
      </dl>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <Filter
          label="Pipeline"
          onChange={setPipeline}
          options={[
            { value: "all", label: "All" },
            { value: "still-campaign", label: "Still" },
            { value: "motion-spot", label: "Motion" },
            { value: "voiceover-pack", label: "Voice" },
            { value: "regenerate", label: "Regeneration" },
          ]}
          value={pipeline}
        />
        <Filter
          label="Outcome"
          onChange={setOutcome}
          options={[
            { value: "all", label: "All" },
            { value: "succeeded", label: "Succeeded" },
            { value: "blocked", label: "Blocked" },
            { value: "failed", label: "Failed" },
          ]}
          value={outcome}
        />
      </div>

      {runs.length === 0 ? (
        <EmptyState
          description="No run in the committed corpus matches this combination. Clear a filter to see the rest."
          icon={ListOrdered}
          title="Nothing matches those filters"
        />
      ) : (
        <Panel>
          {runs.map((run) => (
            <RunRow key={run.seed_id} run={run} />
          ))}
        </Panel>
      )}

      <p className="text-xs leading-relaxed text-subtle">
        {totals.proofs} of these {totals.all} runs are production proofs; the
        rest are deterministic fixtures, labelled as such and never presented as
        paid provider calls. Live API history is shown separately above and is
        never blended into these committed totals.
      </p>
    </div>
  );
}
