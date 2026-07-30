"use client";

import {
  AudioLines,
  ChevronRight,
  Clapperboard,
  ImageIcon,
  ListOrdered,
  RotateCcw,
} from "lucide-react";
import { useMemo, useState } from "react";

import { EventStream, type RunEvent } from "@/components/dara/event-stream";
import { derivePhases } from "@/components/dara/run-phases";
import {
  Badge,
  EmptyState,
  Panel,
  Stepper,
  cn,
  type Tone,
} from "@/components/ui";

import demoSeedData from "../../../api/seeds/demo-runs.json";
import { demoSeedCorpusSchema, type DemoSeedRun } from "../../demo-seed-schema";

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

export function RunsScreen() {
  const [pipeline, setPipeline] = useState<string>("all");
  const [outcome, setOutcome] = useState<string>("all");

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
        <Badge dot tone="warn">
          Committed corpus
        </Badge>
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
        paid provider calls. The API exposes no run-listing endpoint, so this is
        the committed corpus rather than live history.
      </p>
    </div>
  );
}
