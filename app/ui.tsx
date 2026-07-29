"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  apiErrorSchema,
  type VerificationResponse,
  verificationResponseSchema,
} from "./verification-schema";
import {
  liveRunSchema,
  regenerationDiffSchema,
  type LiveRun,
  type RegenerationDiff,
} from "./run-schema";
import {
  ledgerDashboardSchema,
  type LedgerQuery,
  type LedgerSummary,
} from "./ledger-schema";
import { recordedLedgerProof } from "./ledger-proof";
import { publicShareSchema, type PublicShare } from "./share-schema";
import demoSeedData from "../api/seeds/demo-runs.json";
import {
  demoSeedCorpusSchema,
  type DemoSeedRun,
} from "./demo-seed-schema";

type EventItem = {
  seq: number;
  time: string;
  provider: string;
  model: string;
  message: string;
  type: "normal" | "failover" | "revised" | "success";
  replayDelayMs?: number;
};

const demoCorpus = demoSeedCorpusSchema.parse(demoSeedData);
const defaultDemoRun = demoCorpus.runs.find(
  (run) => run.seed_id === demoCorpus.default_seed_id,
) as DemoSeedRun;

function seededEvents(run: DemoSeedRun): EventItem[] {
  return run.events.map((event, index) => ({
    seq: index + 1,
    time: `${(event.at_ms / 1000).toFixed(2)}s`,
    provider: event.provider,
    model: event.model,
    message: event.message,
    type:
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
    replayDelayMs: Math.min(2800, 100 + event.at_ms * 0.04),
  }));
}

const fullEvents = seededEvents(defaultDemoRun);

function liveEvents(run: LiveRun): EventItem[] {
  const started = new Date(run.created_at).getTime();
  return run.events.map((event) => {
    const elapsed = Math.max(0, new Date(event.at).getTime() - started) / 1000;
    return {
      seq: event.seq,
      time: `${elapsed.toFixed(2)}s`,
      provider: event.provider ?? "dara",
      model: event.model ?? event.type,
      message: event.message,
      type:
        event.type === "run.failed"
          ? "failover"
          : event.type === "agent.iteration.evaluated"
            ? event.message.includes("passed")
              ? "success"
              : "revised"
          : event.type === "run.completed" || event.type === "publish.completed"
            ? "success"
            : "normal",
    };
  });
}

function VersionTree({ runs }: { runs: LiveRun[] }) {
  const versions = runs.flatMap((run, runIndex) =>
    run.attempts.length > 0
      ? run.attempts.map((attempt) => ({
          key: `${run.job_id}:${attempt.genblaze_run_id}`,
          index: attempt.attempt,
          generation: runIndex + 1,
          label:
            attempt.status === "rejected"
              ? "Generated, then rejected by visual QA"
              : attempt.status === "failed"
                ? "Provider attempt failed and was preserved"
                : attempt.status === "approved"
                  ? "Generated, approved, embedded, and published"
                  : "Generation attempt in progress",
          detail: `${attempt.genblaze_run_id.slice(0, 8)} · ${
            attempt.parent_run_id
              ? `parent ${attempt.parent_run_id.slice(0, 8)}`
              : "root"
          }`,
          score:
            attempt.qa_score == null
              ? "QA —"
              : `QA ${Math.round(attempt.qa_score * 100)}`,
          status: attempt.status,
        }))
      : [
          {
            key: run.job_id,
            index: 1,
            generation: runIndex + 1,
            label:
              run.status === "succeeded"
                ? "Recorded run completed before attempt tracking"
                : "Recorded run preserved",
            detail: `${run.genblaze_run_id?.slice(0, 8) ?? run.job_id.slice(-8)} · ${
              run.parent_job_id ? "regeneration" : "root"
            }`,
            score:
              run.qa_score == null ? "QA —" : `QA ${Math.round(run.qa_score * 100)}`,
            status: run.status === "succeeded" ? "approved" : "failed",
          },
        ],
  );

  return (
    <div className="version-tree">
      {versions.map((version) => (
        <div className="version-row" key={version.key}>
          <span className="version-index mono">
            {version.generation}.{version.index}
          </span>
          <span>
            <strong>{version.label}</strong>
            <small className="mono">{version.detail}</small>
          </span>
          <span className="mono">{version.score}</span>
          <Badge
            type={
              version.status === "approved"
                ? "allow"
                : version.status === "running"
                  ? "warn"
                  : "block"
            }
          >
            {version.status}
          </Badge>
        </div>
      ))}
    </div>
  );
}

const hash =
  "efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25";

function formatSpend(value: number) {
  return value < 0.1 ? value.toFixed(3) : value.toFixed(2);
}

type PolicySimulation = {
  estimate: {
    expected_usd: string;
    worst_case_usd: string;
  };
  decision: {
    outcome: "allow" | "warn" | "block";
    violations: Array<{ code: string; message: string }>;
  };
};

const navItems = [
  ["/", "Studio"],
  ["/ledger", "Ledger"],
  ["/verify", "Verify"],
];

function Shell({
  children,
  current,
}: {
  children: React.ReactNode;
  current: string;
}) {
  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand display" href="/">
          <span className="brand-mark">D</span>
          DARA
        </Link>
        <nav className="nav" aria-label="Primary navigation">
          {navItems.map(([href, label]) => (
            <Link className={current === href ? "active" : ""} href={href} key={href}>
              {label}
            </Link>
          ))}
          <Link className={current.startsWith("/assets") ? "active" : ""} href="/assets/ast_nw_003">
            Assets
          </Link>
        </nav>
        <div className="workspace">
          <span className="live-dot" />
          Demo workspace · B2 connected
        </div>
      </header>
      {children}
    </main>
  );
}

function Badge({
  type,
  children,
}: {
  type: "allow" | "warn" | "block";
  children: React.ReactNode;
}) {
  return <span className={`policy-badge ${type}`}>{children}</span>;
}

export function HashDisplay({ value = hash }: { value?: string }) {
  return (
    <div className="hash-display static-hash mono" aria-label={`SHA-256 ${value}`}>
      {value.match(/.{1,8}/g)?.map((part, index) => (
        <span className="hash-block" key={`${part}-${index}`}>
          {part}
        </span>
      ))}
    </div>
  );
}

function VerificationHash({
  uploaded,
  expected,
  verified,
}: {
  uploaded: string;
  expected?: string | null;
  verified: boolean;
}) {
  const firstDifference =
    expected && uploaded !== expected
      ? Array.from(uploaded).findIndex((character, index) => character !== expected[index])
      : -1;

  function blocks(value: string, diff = false) {
    return value.match(/.{1,8}/g)?.map((part, blockIndex) => (
      <span className="hash-block" key={`${part}-${blockIndex}`}>
        {Array.from(part).map((character, characterIndex) => {
          const index = blockIndex * 8 + characterIndex;
          const mismatched = diff && firstDifference >= 0 && index >= firstDifference;
          return (
            <span
              className={mismatched ? "hash-character mismatch" : "hash-character"}
              key={`${character}-${index}`}
            >
              {character}
            </span>
          );
        })}
      </span>
    ));
  }

  return (
    <div className={`verification-hashes ${verified ? "is-verified" : ""}`}>
      <div className="hash-display mono" aria-label={`Uploaded SHA-256 ${uploaded}`}>
        {blocks(uploaded, true)}
      </div>
      {expected && expected !== uploaded ? (
        <div className="expected-hash">
          <span className="eyebrow">Expected published SHA-256</span>
          <div className="hash-display mono" aria-label={`Expected SHA-256 ${expected}`}>
            {blocks(expected)}
          </div>
        </div>
      ) : null}
    </div>
  );
}

export function Studio() {
  const [prompt, setPrompt] = useState(
    "Hero shot of a ceramic bowl on washed linen, morning light, quiet editorial composition"
  );
  const [variants, setVariants] = useState(3);
  const [policy, setPolicy] = useState("standard");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [runMode, setRunMode] = useState<"demo" | "live">("demo");
  const [liveRun, setLiveRun] = useState<LiveRun | null>(null);
  const [events, setEvents] = useState(fullEvents);
  const [runState, setRunState] = useState<"ready" | "running" | "done">("done");
  const simulationKey = `${runMode}:${policy}:${aspectRatio}:${variants}`;
  const [simulationResult, setSimulationResult] = useState<{
    key: string;
    value: PolicySimulation;
  } | null>(null);
  const simulation =
    simulationResult?.key === simulationKey ? simulationResult.value : null;
  const [policyStatus, setPolicyStatus] = useState<"checking" | "live" | "fallback">("checking");
  const [runMessage, setRunMessage] = useState("");
  const [toast, setToast] = useState("");
  const [regenerationBase, setRegenerationBase] = useState<LiveRun | null>(null);
  const [regenerationDiff, setRegenerationDiff] =
    useState<RegenerationDiff | null>(null);
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const eventSource = useRef<EventSource | null>(null);

  const localEstimate = useMemo(
    () => (runMode === "live" ? 0.02 : 0.01 * variants),
    [runMode, variants],
  );
  const estimate = simulation
    ? Number(simulation.estimate.expected_usd)
    : localEstimate;
  const worstCase = simulation
    ? Number(simulation.estimate.worst_case_usd)
    : localEstimate * 3;
  const blocked = simulation
    ? simulation.decision.outcome === "block"
    : policy === "locked" && (worstCase > 0.02 || aspectRatio !== "1:1");
  const violationMessage = simulation?.decision.violations[0]?.message
    ?? "The selected brief exceeds the locked policy. Nothing will be spent.";

  useEffect(() => {
    const controller = new AbortController();
    const requestKey = `${runMode}:${policy}:${aspectRatio}:${variants}`;
    const timer = setTimeout(async () => {
      setPolicyStatus("checking");
      try {
        const response = await fetch(
          `/api/policies/pol_${policy}/simulate`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              tenant_id: "demo",
              job_id: "job_studio_preview",
              provider: "openai",
              model: "gpt-image-2",
              modality: "image",
              aspect_ratio: aspectRatio,
              variants,
              max_attempts: 3,
              step_count: 1,
              qa_enabled: runMode === "live",
              prompt_expansion: runMode === "live",
            }),
            signal: controller.signal,
          },
        );
        if (!response.ok) throw new Error("Policy preview unavailable");
        setSimulationResult({
          key: requestKey,
          value: await response.json() as PolicySimulation,
        });
        setPolicyStatus("live");
      } catch (error) {
        if ((error as Error).name !== "AbortError") setPolicyStatus("fallback");
      }
    }, 180);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [aspectRatio, policy, runMode, variants]);

  useEffect(
    () => () => {
      timers.current.forEach(clearTimeout);
      eventSource.current?.close();
    },
    [],
  );

  function applyLiveRun(current: LiveRun) {
    setLiveRun(current);
    setEvents(liveEvents(current));
    if (current.status === "succeeded") {
      setRunState("done");
      if (current.parent_job_id) {
        void loadRegenerationDiff(current.job_id, current.parent_job_id);
      }
      return true;
    }
    if (current.status === "failed" || current.status === "blocked") {
      setRunState("done");
      setRunMessage(
        current.error_message
          ?? "The live job stopped. Its recorded events remain available.",
      );
      return true;
    }
    return false;
  }

  async function loadRegenerationDiff(jobId: string, against: string) {
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(jobId)}/diff?against=${encodeURIComponent(against)}`,
        { cache: "no-store" },
      );
      const json: unknown = await response.json();
      if (!response.ok) {
        const parsed = apiErrorSchema.safeParse(json);
        throw new Error(
          parsed.success
            ? parsed.data.error.message
            : "Dara could not compare the regenerated asset.",
        );
      }
      setRegenerationDiff(regenerationDiffSchema.parse(json));
    } catch (error) {
      setRunMessage(
        error instanceof Error
          ? error.message
          : "Dara could not compare the regenerated asset.",
      );
    }
  }

  async function pollLiveRun(jobId: string) {
    try {
      const response = await fetch(`/api/runs/${encodeURIComponent(jobId)}`, {
        cache: "no-store",
      });
      const json: unknown = await response.json();
      if (!response.ok) {
        const parsed = apiErrorSchema.safeParse(json);
        throw new Error(
          parsed.success
            ? parsed.data.error.message
            : "Dara could not read the live job status.",
        );
      }
      const current = liveRunSchema.parse(json);
      if (applyLiveRun(current)) return;
      const timer = setTimeout(() => void pollLiveRun(jobId), 1200);
      timers.current.push(timer);
    } catch (error) {
      setRunState("done");
      setRunMessage(
        error instanceof Error
          ? error.message
          : "Dara could not read the live job status.",
      );
    }
  }

  function streamLiveRun(jobId: string) {
    eventSource.current?.close();
    const stream = new EventSource(
      `/api/runs/${encodeURIComponent(jobId)}/events`,
    );
    eventSource.current = stream;
    let finished = false;
    let fallbackStarted = false;

    stream.addEventListener("run.snapshot", (message) => {
      try {
        const current = liveRunSchema.parse(
          JSON.parse((message as MessageEvent<string>).data) as unknown,
        );
        if (applyLiveRun(current)) {
          finished = true;
          stream.close();
          if (eventSource.current === stream) eventSource.current = null;
        }
      } catch {
        stream.close();
        if (!fallbackStarted) {
          fallbackStarted = true;
          void pollLiveRun(jobId);
        }
      }
    });
    stream.addEventListener("run.error", () => {
      stream.close();
      if (!fallbackStarted) {
        fallbackStarted = true;
        void pollLiveRun(jobId);
      }
    });
    stream.onerror = () => {
      stream.close();
      if (eventSource.current === stream) eventSource.current = null;
      if (!finished && !fallbackStarted) {
        fallbackStarted = true;
        void pollLiveRun(jobId);
      }
    };
  }

  async function runBrief() {
    if (blocked) return;
    timers.current.forEach(clearTimeout);
    eventSource.current?.close();
    eventSource.current = null;
    setEvents([]);
    setRunState("running");
    setRunMessage("");
    setLiveRun(null);
    setRegenerationBase(null);
    setRegenerationDiff(null);
    if (runMode === "live") {
      try {
        const response = await fetch("/api/runs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            project_id: "prj_dara_live",
            policy_id: `pol_${policy}`,
            prompt,
            aspect_ratio: aspectRatio,
            variants: 1,
          }),
        });
        const json: unknown = await response.json();
        if (!response.ok) {
          const parsed = apiErrorSchema.safeParse(json);
          throw new Error(
            parsed.success
              ? parsed.data.error.message
              : "Dara could not start the live image job.",
          );
        }
        const created = liveRunSchema.parse(json);
        setLiveRun(created);
        setEvents(liveEvents(created));
        streamLiveRun(created.job_id);
      } catch (error) {
        setRunState("done");
        setRunMessage(
          error instanceof Error
            ? error.message
            : "Dara could not start the live image job.",
        );
      }
      return;
    }
    if (policyStatus !== "live") {
      setRunMessage("The policy service could not be reached, so Dara is replaying the verified record without making a provider call.");
    }
    fullEvents.forEach((event, index) => {
      const timer = setTimeout(() => {
        setEvents((current) => [...current, event]);
        if (index === fullEvents.length - 1) setRunState("done");
      }, event.replayDelayMs ?? index * 360);
      timers.current.push(timer);
    });
  }

  async function regenerate() {
    if (!liveRun || liveRun.status !== "succeeded") return;
    timers.current.forEach(clearTimeout);
    eventSource.current?.close();
    setRegenerationBase(liveRun);
    setRegenerationDiff(null);
    setEvents([]);
    setRunState("running");
    setRunMessage("Reconstructing the recorded manifest and reapplying policy.");
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(liveRun.job_id)}/regenerate`,
        { method: "POST" },
      );
      const json: unknown = await response.json();
      if (!response.ok) {
        const parsed = apiErrorSchema.safeParse(json);
        throw new Error(
          parsed.success
            ? parsed.data.error.message
            : "Dara could not start the regeneration.",
        );
      }
      const created = liveRunSchema.parse(json);
      setLiveRun(created);
      setEvents(liveEvents(created));
      setRunMessage("");
      streamLiveRun(created.job_id);
    } catch (error) {
      setRunState("done");
      setRunMessage(
        error instanceof Error
          ? error.message
          : "Dara could not start the regeneration.",
      );
    }
  }

  function approve() {
    setToast("Already approved · trusted published hash is on record");
    setTimeout(() => setToast(""), 2200);
  }

  return (
    <Shell current="/">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Generation control plane</p>
            <h1 className="page-title display">Make the work.<br />Keep the record.</h1>
            <p className="page-lede">
              Governed media pipelines with visible policy, honest cost, and provenance that survives the handoff.
            </p>
          </div>
          <Badge type={blocked ? "block" : policyStatus === "live" ? "allow" : "warn"}>
            {blocked
              ? "Pre-flight blocked"
              : policyStatus === "live"
                ? "Live policy active"
                : policyStatus === "checking"
                  ? "Checking policy"
                  : "Demo policy preview"}
          </Badge>
        </div>

        <div className="studio-grid">
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">New brief</h2>
              <span className="mono hash-short">JOB / DRAFT</span>
            </div>
            <div className="form">
              <div className="field">
                <span className="label">Run mode</span>
                <div className="segmented mode-switch" role="group" aria-label="Run mode">
                  <button
                    className={runMode === "demo" ? "selected" : ""}
                    onClick={() => {
                      setRunMode("demo");
                      eventSource.current?.close();
                      setVariants(3);
                      setLiveRun(null);
                      setRegenerationBase(null);
                      setRegenerationDiff(null);
                      setEvents(fullEvents);
                      setRunState("done");
                      setRunMessage("");
                    }}
                    type="button"
                  >
                    Demo replay · $0
                  </button>
                  <button
                    className={runMode === "live" ? "selected" : ""}
                    onClick={() => {
                      setRunMode("live");
                      eventSource.current?.close();
                      setVariants(1);
                      setLiveRun(null);
                      setRegenerationBase(null);
                      setRegenerationDiff(null);
                      setEvents([]);
                      setRunState("ready");
                      setRunMessage("");
                    }}
                    type="button"
                  >
                    Live OpenAI · spends
                  </button>
                </div>
                {runMode === "live" ? (
                  <small className="live-mode-note">
                    One candidate at a time, scored by OpenAI vision. Dara may revise up to three times inside the reserved cap.
                  </small>
                ) : (
                  <small className="live-mode-note">
                    Defaulting to a clearly labelled deterministic fixture from {demoCorpus.runs.length} committed seed runs. Production proofs and fixtures are never conflated; live generation requires the separate control above.
                  </small>
                )}
              </div>
              <div className="field">
                <label htmlFor="project">Project</label>
                <select id="project" defaultValue="northwind">
                  <option value="northwind">Northwind — Q3 campaign</option>
                  <option value="atlas">Atlas Hotels — Brand film</option>
                  <option value="field">Field Notes — Product launch</option>
                </select>
              </div>
              <div className="two-col">
                <div className="field">
                  <label htmlFor="pipeline">Pipeline</label>
                  <select id="pipeline" defaultValue="still">
                    <option value="still">Still campaign</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="policy">Policy</label>
                  <select id="policy" value={policy} onChange={(e) => setPolicy(e.target.value)}>
                    <option value="permissive">Permissive</option>
                    <option value="standard">Standard client work</option>
                    <option value="locked">Locked demo · $0.02 max</option>
                  </select>
                </div>
              </div>
              <div className="field">
                <label htmlFor="prompt">Prompt</label>
                <textarea id="prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
              </div>
              <div className="field">
                <span className="label">Aspect ratio</span>
                <div className="segmented" role="group" aria-label="Aspect ratio">
                  {[
                    ["1:1", "Square"],
                    ["3:2", "Landscape"],
                    ["2:3", "Portrait"],
                  ].map(([value, label]) => (
                    <button
                      className={aspectRatio === value ? "selected" : ""}
                      key={value}
                      onClick={() => setAspectRatio(value)}
                      type="button"
                    >
                      {label} · {value}
                    </button>
                  ))}
                </div>
              </div>
              <div className="field">
                <label htmlFor="variants">Variants · {variants}</label>
                <input
                  id="variants"
                  disabled={runMode === "live"}
                  max={runMode === "live" ? "1" : "4"}
                  min="1"
                  onChange={(e) => setVariants(Number(e.target.value))}
                  type="range"
                  value={variants}
                />
              </div>
              <div className={`estimate ${blocked ? "blocked" : ""}`}>
                <div className="estimate-row">
                  <div>
                    <span className="label">Live estimate</span>
                    <small>
                      Expected / three-attempt reserve · {policyStatus === "live" ? "from Dara API" : "local preview"}
                    </small>
                  </div>
                  <strong className="mono">${formatSpend(estimate)} / ${formatSpend(worstCase)}</strong>
                </div>
                <div className="estimate-track">
                  <div className="estimate-fill" style={{ width: `${Math.min(100, (worstCase / 0.12) * 100)}%` }} />
                </div>
                {blocked ? (
                  <p className="policy-message">
                    {violationMessage} No provider will be called.
                  </p>
                ) : null}
              </div>
              {runMessage ? <p className="policy-message" role="status">{runMessage}</p> : null}
              <button className="primary-btn" disabled={blocked || !prompt.trim()} onClick={() => void runBrief()} type="button">
                {blocked
                  ? "Blocked before spend"
                  : runState === "running"
                    ? runMode === "live"
                      ? "Generating with OpenAI…"
                      : "Replay in progress…"
                    : runMode === "live"
                      ? "Generate one live image"
                      : "Run verified demo"}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">
                {runMode === "live" ? "Live still · OpenAI to B2" : defaultDemoRun.title}
              </h2>
              <span
                className={`status ${
                  liveRun?.status === "failed"
                    ? "status-failed"
                    : runState === "running"
                      ? "status-running"
                      : "status-verified"
                }`}
              >
                {runMode === "live"
                  ? liveRun?.status ?? (runState === "running" ? "starting" : "ready")
                  : runState === "running"
                    ? "Replaying"
                    : "Verified"}
              </span>
            </div>
            <div className="run-summary">
              <div className="metric">
                <span>Run</span>
                <strong className="mono">
                  {liveRun ? liveRun.job_id.slice(-8).toUpperCase() : runMode === "live" ? "NEW" : defaultDemoRun.seed_id.slice(-8).toUpperCase()}
                </strong>
              </div>
              <div className="metric"><span>Provider</span><strong className="mono">{runMode === "live" ? "OpenAI" : defaultDemoRun.provider}</strong></div>
              <div className="metric"><span>Model</span><strong className="mono">{runMode === "live" ? "gpt-image-2" : defaultDemoRun.model}</strong></div>
              <div className="metric">
                <span>Vision QA</span>
                <strong className="mono">
                  {liveRun?.qa_score != null
                    ? `${Math.round(liveRun.qa_score * 100)} / 100`
                    : runMode === "live"
                      ? "PENDING"
                      : defaultDemoRun.qa_score == null
                        ? "—"
                        : `${Math.round(defaultDemoRun.qa_score * 100)} / 100`}
                </strong>
              </div>
              <div className="metric">
                <span>{liveRun?.actual_cost_usd ? "Recorded cost" : "Reserve"}</span>
                <strong className="mono">
                  ${liveRun?.actual_cost_usd ?? liveRun?.worst_case_cost_usd ?? (runMode === "demo" ? defaultDemoRun.cost_usd : formatSpend(worstCase))}
                </strong>
              </div>
            </div>
            {liveRun?.policy_decisions.length ? (
              <div className="policy-audit">
                {liveRun.policy_decisions.map((decision, index) => (
                  <div
                    className={`policy-audit-row ${decision.outcome}`}
                    key={`${decision.enforcement_point}-${index}`}
                  >
                    <span className="mono">
                      {decision.enforcement_point.replace("_", " ")}
                    </span>
                    <strong>{decision.outcome}</strong>
                    <span>
                      {decision.violations.length
                        ? decision.violations.map((item) => item.message).join(" ")
                        : `Allowed with a $${decision.estimated_cost_usd} worst-case reservation.`}
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
            <div className="stream" aria-live="polite">
              {events.length === 0 ? (
                <div className="stream-empty">
                  {runMode === "live"
                    ? "Choose Generate one live image to start an authenticated job."
                    : "Replay events will appear here."}
                </div>
              ) : null}
              {events.map((event) => (
                <div className={`event mono ${event.type}`} key={event.seq}>
                  <span className="event-seq">{String(event.seq).padStart(2, "0")}</span>
                  <span className="event-time">{event.time}</span>
                  <span className="event-provider">{event.provider}</span>
                  <div>{event.message}</div>
                  <span className={`event-tag ${event.type === "success" ? "allow" : ""}`}>
                    {event.type === "success" ? "sealed" : "event"}
                  </span>
                </div>
              ))}
            </div>
            {runMode === "live" && liveRun ? (
              <>
                <div className="panel-head">
                  <h2 className="panel-title">Version history</h2>
                  <span className="mono hash-short">
                    {liveRun.attempts.length || 1} ATTEMPT
                    {(liveRun.attempts.length || 1) === 1 ? "" : "S"}
                  </span>
                </div>
                <VersionTree
                  runs={
                    regenerationBase
                      ? [regenerationBase, liveRun]
                      : [liveRun]
                  }
                />
              </>
            ) : null}
            {runMode === "demo" && runState === "done" ? (
              <div className="result-strip">
                <p><strong>The deterministic QA-revision fixture is ready.</strong><br />Two attempts and parent lineage are replayed without claiming a live provider call or settled spend.</p>
                <button className="secondary-btn" onClick={approve} type="button">Approve</button>
              </div>
            ) : null}
            {runMode === "live" && liveRun?.status === "succeeded" ? (
              <div className="result-strip live-result">
                {liveRun.asset_url ? (
                  // B2 signs this short-lived URL at runtime, so it cannot use a static Next image allowlist.
                  // eslint-disable-next-line @next/next/no-img-element
                  <img alt="Newly generated Dara still" src={liveRun.asset_url} />
                ) : null}
                <p>
                  <strong>Live asset published.</strong><br />
                  Vision QA passed in {liveRun.qa_attempts} attempt{liveRun.qa_attempts === 1 ? "" : "s"}; Genblaze manifest embedded and hashes recorded in B2.
                </p>
                {liveRun.asset_url ? (
                  <a
                    className="secondary-btn"
                    href={liveRun.asset_url}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Open asset
                  </a>
                ) : null}
                <button
                  className="secondary-btn"
                  onClick={() => void regenerate()}
                  type="button"
                >
                  Regenerate from manifest
                </button>
              </div>
            ) : null}
          </section>
        </div>
        {regenerationDiff ? (
          <section className="panel regeneration-diff">
            <div className="panel-head">
              <h2 className="panel-title">Regeneration diff</h2>
              <span className="mono hash-short">
                {regenerationDiff.lineage_verified
                  ? "LINEAGE VERIFIED"
                  : "LINEAGE INCOMPLETE"}
              </span>
            </div>
            <div className="diff-assets">
              {[
                ["Original", regenerationDiff.original],
                ["Regenerated", regenerationDiff.regenerated],
              ].map(([label, run]) => {
                const comparedRun = run as LiveRun;
                return (
                  <article className="diff-asset" key={label as string}>
                    <span className="eyebrow">{label as string}</span>
                    {comparedRun.asset_url ? (
                      // B2 signs these short-lived comparison URLs at request time.
                      // eslint-disable-next-line @next/next/no-img-element
                      <img
                        alt={`${label as string} Dara asset`}
                        src={comparedRun.asset_url}
                      />
                    ) : (
                      <div className="diff-asset-missing">Preview unavailable</div>
                    )}
                    <span className="mono">
                      {comparedRun.published_sha256?.slice(0, 16) ?? "hash pending"}…
                    </span>
                  </article>
                );
              })}
            </div>
            <div className="diff-table" role="table" aria-label="Regeneration parameters">
              <div className="diff-row diff-head" role="row">
                <span>Parameter</span>
                <span>Original</span>
                <span>Regenerated</span>
                <span>Result</span>
              </div>
              {regenerationDiff.parameters.map((parameter) => (
                <div className="diff-row" role="row" key={parameter.name}>
                  <strong>{parameter.name}</strong>
                  <span className="mono">{String(parameter.original ?? "—")}</span>
                  <span className="mono">{String(parameter.regenerated ?? "—")}</span>
                  <Badge type={parameter.match ? "allow" : "warn"}>
                    {parameter.match ? "Matched" : "Drifted"}
                  </Badge>
                </div>
              ))}
            </div>
            <p className="trust-note">{regenerationDiff.non_deterministic_note}</p>
          </section>
        ) : null}
      </section>
      {toast ? <div className="toast" role="status">{toast}</div> : null}
    </Shell>
  );
}

const ledgerRows = [
  ["F1A333", "Dara — provenance proof", "gpt-image-2", "Image", "$0.01*", "—", "Approved", 100],
];

export function Ledger() {
  const [live, setLive] = useState<{
    summary: LedgerSummary;
    models: LedgerQuery;
    projects: LedgerQuery;
    months: LedgerQuery;
  } | null>(null);
  const [ledgerState, setLedgerState] = useState<"loading" | "live" | "fallback">(
    "loading",
  );

  useEffect(() => {
    const controller = new AbortController();
    async function loadLedger() {
      try {
        const response = await fetch("/api/ledger/dashboard", {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Ledger unavailable");
        }
        setLive(ledgerDashboardSchema.parse(await response.json()));
        setLedgerState("live");
      } catch (error) {
        if ((error as Error).name !== "AbortError") {
          setLive(recordedLedgerProof);
          setLedgerState("fallback");
        }
      }
    }
    void loadLedger();
    return () => controller.abort();
  }, []);

  const summary = live?.summary;
  const modelRows = live?.models.rows ?? [];
  const projectRows = live?.projects.rows ?? [];
  const monthRows = live?.months.rows ?? [];

  return (
    <Shell current="/ledger">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Spend ledger</p>
            <h1 className="page-title display">The honest numbers.</h1>
            <p className="page-lede">Every attempt counts—including the work that never shipped.</p>
          </div>
          <span className="mono hash-short">
            {ledgerState === "live" ? "LIVE · DUCKDB OVER B2" : "RECORDED PROOF"}
          </span>
        </div>
        <div className="headline-metrics">
          <div className="headline-metric">
            <span>Published assets</span>
            <strong className="mono">{summary?.approved_assets ?? 1}</strong>
            <small>{summary ? `${summary.run_count} accounted runs` : "Real OpenAI → Genblaze → B2 proof"}</small>
          </div>
          <div className="headline-metric">
            <span>Spend prevented</span>
            <strong className="mono">${summary?.spend_prevented_usd ?? "0.090000"}</strong>
            <small>Policy-blocked work · zero provider calls</small>
          </div>
          <div className="headline-metric">
            <span>Cost / approved asset</span>
            <strong className="mono">${summary?.cost_per_approved_asset_usd ?? "0.010000"}</strong>
            <small>{summary ? `Waste ratio ${(Number(summary.waste_ratio) * 100).toFixed(1)}%` : "Includes discarded attempts"}</small>
          </div>
        </div>
        <div className="filterbar" aria-label="Ledger filters">
          <span className="mono ledger-source">
            {ledgerState === "loading"
              ? "Opening B2 ledger…"
              : ledgerState === "live"
                ? `Generated ${new Date(summary?.generated_at ?? "").toLocaleTimeString()}`
                : "Live ledger unavailable · verified B2 snapshot from 29 Jul 2026"}
          </span>
        </div>
        <div className="data-panel">
          <table>
            <thead><tr><th>Model</th><th>Provider</th><th>Runs</th><th>Total spend</th><th>Mean / run</th></tr></thead>
            <tbody>
              {modelRows.length ? modelRows.map((row) => (
                <tr key={`${row[0]}-${row[1]}`}>
                  <td className="mono">{row[0]}</td><td>{row[1]}</td>
                  <td className="mono">{row[2]}</td>
                  <td className="mono">${row[3]}</td><td className="mono">${row[4]}</td>
                </tr>
              )) : ledgerRows.map((row) => (
                <tr key={row[0]}><td className="mono">{row[2]}</td><td>openai</td><td>1</td><td className="mono">{row[4]}</td><td className="mono">{row[4]}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="ledger-split">
          <div className="data-panel">
            <div className="panel-head"><h2 className="panel-title">Spend by project</h2></div>
            <table>
              <thead><tr><th>Project</th><th>Runs</th><th>Approved</th><th>Spend</th></tr></thead>
              <tbody>{projectRows.map((row) => (
                <tr key={String(row[0])}>
                  <td className="mono">{row[0]}</td>
                  <td>{row[1]}</td>
                  <td>{row[2]}</td>
                  <td className="mono">{row[3] == null ? "—" : `$${row[3]}`}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="data-panel">
            <div className="panel-head"><h2 className="panel-title">Spend by month</h2></div>
            <table>
              <thead><tr><th>Month</th><th>Runs</th><th>Spend</th></tr></thead>
              <tbody>{monthRows.map((row) => (
                <tr key={String(row[0])}><td className="mono">{row[0]}</td><td>{row[1]}</td><td className="mono">${row[2]}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
        <p className="trust-note">* Conservative low-quality policy reservation. The provider did not return settled cost in the recorded manifest.</p>
      </section>
    </Shell>
  );
}

const lineage = [
  ["01 · Brief", "Dara policy engine", "Standard client work · pre-flight allow", "$0.00"],
  ["02 · Generate", "openai-dalle / gpt-image-2", "1024×1024 · low quality · PNG", "$0.01*"],
  ["03 · Record", "Genblaze manifest / B2", "Source hash and canonical manifest verified", "$0.00"],
  ["04 · Publish", "Dara publish / B2", "Embedded derivative and published hash indexed", "$0.00"],
];

function Lineage() {
  return (
    <div className="lineage">
      {lineage.map(([step, title, detail, cost]) => (
        <div className="lineage-node" key={step}>
          <span className="lineage-step mono">{step}</span>
          <div className="lineage-main"><strong>{title}</strong><span className="mono">{detail}</span></div>
          <span className="lineage-cost mono">{cost}</span>
        </div>
      ))}
    </div>
  );
}

export function Verify() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("dara-verified-published.png");
  const [result, setResult] = useState<VerificationResponse>({
    result: "embedded",
    verification: "trusted-match",
    storage_status: "available",
    verified: true,
    uploaded_sha256: "efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25",
    expected_published_sha256: "efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25",
    manifest: {
      canonical_hash: "13dc9b8ae977809a90ffcc5b3971a011dc5cbac8c8505df2e7f131fa8a9e9b28",
      hash_matches: true,
      declared_hashes_match: true,
      run_id: "f1a3332d-5727-4644-976a-2f7c09c74e82",
      created_at: "2026-07-29T12:31:10Z",
      steps: [
        {
          provider: "openai-dalle",
          model: "gpt-image-2",
          modality: "image",
          prompt: "Dara command center with a visible provenance thread",
          params: { size: "1024x1024", quality: "low", output_format: "png" },
          cost_usd: null,
        },
      ],
      parent_run_id: null,
      redacted: false,
    },
    lineage: [
      {
        run_id: "f1a3332d-5727-4644-976a-2f7c09c74e82",
        at: "2026-07-29T12:31:10Z",
        relationship: "generated",
        provider: "openai-dalle",
        model: "gpt-image-2",
      },
    ],
    warning: null,
    trust_note:
      "Tamper-evident within the issuing organisation's storage. Not an adversarial authenticity proof.",
  });
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [state, setState] = useState<"ready" | "checking" | "done" | "error">("ready");
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);

  async function chooseFile(file?: File) {
    if (!file) return;
    setFileName(file.name);
    setMode("live");
    setState("checking");
    setMessage("");
    const body = new FormData();
    body.set("file", file);
    try {
      const endpoint = daraApiUrl
        ? `${daraApiUrl}/v1/verify`
        : "/api/verify";
      const response = await fetch(endpoint, { method: "POST", body });
      const responseText = await response.text();
      let json: unknown;
      try {
        json = JSON.parse(responseText);
      } catch {
        throw new Error(
          response.ok
            ? "Dara returned an unreadable verification response."
            : responseText || "Dara could not verify this file. Try again.",
        );
      }
      if (!response.ok) {
        const error = apiErrorSchema.parse(json);
        throw new Error(error.error.message);
      }
      setResult(verificationResponseSchema.parse(json));
      setState("done");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Dara could not verify this file. Try again.",
      );
      setState("error");
    }
  }

  const badgeType =
    result.verification === "trusted-match"
      ? "allow"
      : result.verification === "trusted-mismatch"
        ? "block"
        : "warn";
  const stateTitle = {
    "trusted-match": "Trusted published record match",
    "trusted-mismatch": "Trusted record mismatch",
    "self-consistent": "Internally consistent",
    unknown: "No trusted record",
  }[result.verification];
  const badgeLabel = {
    "trusted-match": "Verified",
    "trusted-mismatch": "Changed",
    "self-consistent": "Untrusted",
    unknown: "Unknown",
  }[result.verification];

  return (
    <Shell current="/verify">
      <section className="page verify-wrap">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Public verification</p>
            <h1 className="page-title display">Check where it came from.</h1>
            <p className="page-lede">No generation provider is contacted. Dara checks the file against its trusted storage record.</p>
          </div>
        </div>
        <input
          accept="image/*,video/*,audio/*"
          hidden
          onChange={(e) => void chooseFile(e.target.files?.[0])}
          ref={inputRef}
          type="file"
        />
        <button
          className={`dropzone ${dragging ? "is-dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void chooseFile(event.dataTransfer.files[0]);
          }}
          type="button"
        >
          <span className="drop-icon">↓</span>
          <h2>{state === "checking" ? "Checking the trusted record…" : "Drop a file to check where it came from"}</h2>
          <p>or choose a file · PNG, JPG, MP4, WAV up to 100 MB</p>
        </button>
        {state === "error" ? (
          <div className="verify-message" role="alert">
            <Badge type="warn">Service status</Badge>
            <p>{message}</p>
            <button
              className="secondary-btn"
              onClick={() => {
                setMode("demo");
                setState("ready");
                setMessage("");
              }}
              type="button"
            >
              Return to verified demo record
            </button>
          </div>
        ) : null}
        {state !== "error" ? (
          <section className="verify-result">
            <div className="hash-label">
              <div>
                <p className="eyebrow">
                  {mode === "demo" ? "Verified demo record" : "Uploaded file"} · {fileName}
                </p>
                <h2 className="panel-title">{stateTitle}</h2>
              </div>
              <Badge type={badgeType}>{badgeLabel}</Badge>
            </div>
            <VerificationHash
              expected={result.expected_published_sha256}
              uploaded={result.uploaded_sha256}
              verified={result.verified}
            />
            {result.warning ? <p className="verification-warning">{result.warning}</p> : null}
            <div className="verification-meta">
              <span>
                Discovery <strong className="mono">{result.result}</strong>
              </span>
              <span>
                Storage <strong className="mono">{result.storage_status}</strong>
              </span>
              {result.manifest ? (
                <span>
                  Manifest <strong className="mono">{result.manifest.hash_matches ? "valid" : "invalid"}</strong>
                </span>
              ) : null}
            </div>
            <div className="lineage">
              {result.lineage.map((item, index) => (
                <div className="lineage-node" key={`${item.run_id}-${index}`}>
                  <span className="lineage-step mono">
                    {String(index + 1).padStart(2, "0")} · {item.relationship}
                  </span>
                  <div className="lineage-main">
                    <strong>{item.provider ?? "Parent run"} / {item.model ?? "record"}</strong>
                    <span className="mono">{item.run_id}</span>
                  </div>
                  <span className="lineage-cost mono">
                    {new Date(item.at).toLocaleDateString("en-US", {
                      month: "short",
                      day: "2-digit",
                      year: "numeric",
                    })}
                  </span>
                </div>
              ))}
            </div>
            <p className="trust-note">
              Trust boundary: {result.trust_note}
            </p>
          </section>
        ) : null}
      </section>
    </Shell>
  );
}

export function AssetDetail() {
  return (
    <Shell current="/assets">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Asset / 9856ED41</p>
            <h1 className="page-title display">Dara provenance proof.</h1>
            <p className="page-lede">Approved deliverable · exact OpenAI generation record preserved.</p>
          </div>
          <Badge type="allow">Verified</Badge>
        </div>
        <section className="panel" style={{ marginBottom: 24 }}>
          <div className="panel-head"><h2 className="panel-title">Published SHA-256</h2><span className="mono hash-short">WHOLE FILE</span></div>
          <div style={{ padding: 16 }}><HashDisplay /></div>
        </section>
        <div className="asset-grid">
          <div>
            <div className="asset-preview" role="img" aria-label="Dara provenance proof generated with OpenAI GPT Image 2" />
            <dl className="asset-meta">
              <div className="detail-row"><dt>Provider / model</dt><dd className="mono">openai-dalle / gpt-image-2</dd></div>
              <div className="detail-row"><dt>Source hash</dt><dd className="mono">97f3532e…7d5f3164</dd></div>
              <div className="detail-row"><dt>Published hash</dt><dd className="mono">efaf24d3…20244c25</dd></div>
              <div className="detail-row"><dt>Manifest</dt><dd className="mono">b2://dara/manifests/f1a3332d….json</dd></div>
              <div className="detail-row"><dt>Provider latency</dt><dd className="mono">29.369s</dd></div>
            </dl>
          </div>
          <div className="panel">
            <div className="panel-head"><h2 className="panel-title">Lineage</h2><span className="mono hash-short">4 EVENTS</span></div>
            <div style={{ padding: "0 18px 24px" }}><Lineage /></div>
            <div className="panel-head"><h2 className="panel-title">Version history</h2><span className="mono hash-short">1 RECORDED RUN</span></div>
            <div className="version-row"><span className="version-index mono">01</span><span>Generated, embedded, and published</span><span className="mono">HASH OK</span><Badge type="allow">Approved</Badge></div>
          </div>
        </div>
      </section>
    </Shell>
  );
}

function DisclosureMedia({ share }: { share: PublicShare }) {
  const asset = share.assets[0];
  const alt = "AI-generated media disclosed through Dara";
  if (asset.mime_type.startsWith("video/")) {
    return <video className="shared-media" controls src={asset.url} aria-label={alt} />;
  }
  if (asset.mime_type.startsWith("audio/")) {
    return (
      <div className="shared-audio">
        <p className="eyebrow">Audio disclosure</p>
        <audio controls src={asset.url} aria-label={alt} />
      </div>
    );
  }
  // The API supplies a short-lived B2 URL, so it cannot use a static image allowlist.
  // eslint-disable-next-line @next/next/no-img-element
  return <img className="shared-media" src={asset.url} alt={alt} />;
}

export function ShareView({ token }: { token: string }) {
  const [share, setShare] = useState<PublicShare | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/share/${encodeURIComponent(token)}`, {
          cache: "no-store",
        });
        const body: unknown = await response.json();
        if (!response.ok) {
          const parsed = apiErrorSchema.safeParse(body);
          throw new Error(
            parsed.success
              ? parsed.data.error.message
              : "This disclosure could not be loaded.",
          );
        }
        const parsed = publicShareSchema.safeParse(body);
        if (!parsed.success) {
          throw new Error("The disclosure response did not pass validation.");
        }
        if (active) setShare(parsed.data);
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "This disclosure could not be loaded.",
          );
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [token]);

  const asset = share?.assets[0];
  const generated = asset
    ? new Date(asset.generated_at).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "UTC",
      })
    : null;

  return (
    <main className="share-shell">
      <article className="share-card">
        <div className="page-heading">
          <div>
            <Link className="brand display" href="/" style={{ color: "var(--ink)", marginBottom: 38 }}>
              <span className="brand-mark" style={{ borderColor: "var(--ink)" }}>D</span>DARA
            </Link>
            <p className="eyebrow">Client disclosure / Dara</p>
            <h1 className="page-title display">Provenance proof.</h1>
            <p className="page-lede">
              {share
                ? `Generated media disclosure · issued ${new Date(
                    share.issued_at,
                  ).toLocaleDateString("en-GB", { timeZone: "UTC" })}`
                : "Loading token-scoped disclosure…"}
            </p>
          </div>
          <Badge type={error ? "block" : share ? "allow" : "warn"}>
            {error ? "Unavailable" : share ? "Record matched" : "Checking"}
          </Badge>
        </div>
        {error ? (
          <section className="panel disclosure-error">
            <p className="eyebrow">Disclosure unavailable</p>
            <p>{error}</p>
          </section>
        ) : share && asset ? (
          <>
            <div className="asset-grid">
              <DisclosureMedia share={share} />
              <div>
                <dl className="asset-meta">
                  <div className="detail-row"><dt>Provider</dt><dd>{asset.provider}</dd></div>
                  <div className="detail-row"><dt>Model</dt><dd className="mono">{asset.model}</dd></div>
                  <div className="detail-row"><dt>Generated</dt><dd className="mono">{generated} UTC</dd></div>
                  <div className="detail-row"><dt>Verification</dt><dd>Token-scoped bytes match Dara&apos;s trusted record</dd></div>
                </dl>
                <p className="redaction-note">{share.disclosure} The file is served from a separate token-scoped object with a Genblaze redacted pointer record.</p>
                <p className="trust-note">{share.trust_note}</p>
              </div>
            </div>
            <section className="panel disclosure-hash">
              <div className="panel-head"><h2 className="panel-title">Shared SHA-256</h2><span className="mono hash-short">WHOLE FILE</span></div>
              <div style={{ padding: 16 }}><HashDisplay value={asset.shared_sha256} /></div>
            </section>
          </>
        ) : (
          <section className="panel disclosure-error">
            <p>Checking the exact shared bytes against Dara&apos;s trusted record…</p>
          </section>
        )}
      </article>
    </main>
  );
}
