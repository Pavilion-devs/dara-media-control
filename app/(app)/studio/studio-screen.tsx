"use client";

import {
  AudioLines,
  Ban,
  Clapperboard,
  ImageIcon,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { ActiveEvent, EventStream, type RunEvent } from "@/components/dara/event-stream";
import { derivePhases } from "@/components/dara/run-phases";
import { ShareAction } from "@/components/dara/share-action";
import {
  Badge,
  Button,
  Field,
  Panel,
  PanelBody,
  PanelHead,
  Segmented,
  Select,
  StatusBlock,
  Stepper,
  Textarea,
  cn,
} from "@/components/ui";

import demoSeedData from "../../../api/seeds/demo-runs.json";
import { demoSeedCorpusSchema, type DemoSeedRun } from "../../demo-seed-schema";
import { liveRunSchema, type LiveRun } from "../../run-schema";
import { apiErrorSchema } from "../../verification-schema";

const demoCorpus = demoSeedCorpusSchema.parse(demoSeedData);

type PolicySimulation = {
  estimate: { expected_usd: string; worst_case_usd: string };
  decision: {
    outcome: "allow" | "warn" | "block";
    violations: Array<{ code: string; message: string }>;
  };
};

function formatSpend(value: number) {
  return value < 0.1 ? value.toFixed(3) : value.toFixed(2);
}

function seededEvents(run: DemoSeedRun): RunEvent[] {
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

function replayDelay(run: DemoSeedRun, index: number) {
  return Math.min(2800, 100 + run.events[index].at_ms * 0.04);
}

function liveEvents(run: LiveRun): RunEvent[] {
  const started = new Date(run.created_at).getTime();
  return run.events.map((event) => {
    const elapsed = Math.max(0, new Date(event.at).getTime() - started) / 1000;
    return {
      seq: event.seq,
      time: `${elapsed.toFixed(2)}s`,
      provider: event.provider ?? "dara",
      model: event.model ?? event.type,
      message: event.message,
      kind: event.type,
      tone:
        event.type === "run.failed"
          ? "failover"
          : event.type === "agent.iteration.evaluated"
            ? event.message.includes("passed")
              ? "success"
              : "revised"
            : event.type === "run.completed"
                || event.type === "publish.completed"
              ? "success"
              : "normal",
    } as RunEvent;
  });
}

const pipelineIcon: Record<string, typeof ImageIcon> = {
  "still-campaign": ImageIcon,
  regenerate: ImageIcon,
  "motion-spot": Clapperboard,
  "voiceover-pack": AudioLines,
};

/** The stage: empty intent, live progress, or the finished asset. */
function Stage({
  assetUrl,
  blockedRun,
  pipelineId,
  running,
  started,
}: {
  assetUrl: string | null;
  blockedRun: boolean;
  pipelineId: string;
  running: boolean;
  started: boolean;
}) {
  const Icon = pipelineIcon[pipelineId] ?? ImageIcon;

  if (blockedRun) {
    return (
      <div className="flex aspect-[16/10] flex-col items-center justify-center gap-3 rounded-xl border border-blocked/25 bg-blocked/10 px-6 text-center">
        <Ban aria-hidden className="size-8 text-blocked" />
        <p className="text-sm font-semibold text-blocked-ink">
          Blocked before any provider was called
        </p>
        <p className="max-w-xs text-xs leading-relaxed text-muted">
          Nothing was spent. The rejection itself is recorded in the ledger.
        </p>
      </div>
    );
  }

  if (assetUrl && !running) {
    return (
      // B2 signs live asset URLs at runtime, so no static image allowlist applies.
      <img
        alt="Generated asset produced by this Dara run"
        className="aspect-[16/10] w-full rounded-xl border border-line bg-inset object-cover"
        src={assetUrl}
      />
    );
  }

  return (
    <div
      className={cn(
        "flex aspect-[16/10] flex-col items-center justify-center gap-3 rounded-xl border border-line bg-inset px-6 text-center",
        running && "animate-pulse",
      )}
    >
      <Icon aria-hidden className="size-8 text-faint" strokeWidth={1.5} />
      <p className="text-sm text-subtle">
        {running
          ? "Working…"
          : started
            ? "This run produced no previewable asset."
            : "The generated asset appears here."}
      </p>
    </div>
  );
}

export function StudioScreen() {
  const [seedId, setSeedId] = useState(demoCorpus.default_seed_id);
  const demoRun = useMemo(
    () =>
      demoCorpus.runs.find((run) => run.seed_id === seedId) as DemoSeedRun,
    [seedId],
  );
  const demoEvents = useMemo(() => seededEvents(demoRun), [demoRun]);

  const [prompt, setPrompt] = useState(
    "Hero shot of a ceramic bowl on washed linen, morning light, quiet editorial composition",
  );
  const [variants, setVariants] = useState(3);
  const [policy, setPolicy] = useState("standard");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [runMode, setRunMode] = useState<"demo" | "live">("demo");
  const [liveRun, setLiveRun] = useState<LiveRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>(demoEvents);
  const [runState, setRunState] = useState<"ready" | "running" | "done">("done");
  const simulationKey = `${runMode}:${policy}:${aspectRatio}:${variants}`;
  const [simulationResult, setSimulationResult] = useState<{
    key: string;
    value: PolicySimulation;
  } | null>(null);
  const simulation =
    simulationResult?.key === simulationKey ? simulationResult.value : null;
  const [policyStatus, setPolicyStatus] = useState<
    "checking" | "live" | "fallback"
  >("checking");
  const [runMessage, setRunMessage] = useState("");
  const [toast, setToast] = useState("");
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
  const violationMessage =
    simulation?.decision.violations[0]?.message
    ?? "The selected brief exceeds the locked policy. Nothing will be spent.";

  useEffect(() => {
    const controller = new AbortController();
    const requestKey = `${runMode}:${policy}:${aspectRatio}:${variants}`;
    const timer = setTimeout(async () => {
      setPolicyStatus("checking");
      try {
        const response = await fetch(`/api/policies/pol_${policy}/simulate`, {
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
        });
        if (!response.ok) throw new Error("Policy preview unavailable");
        setSimulationResult({
          key: requestKey,
          value: (await response.json()) as PolicySimulation,
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
      timers.current.push(setTimeout(() => void pollLiveRun(jobId), 1200));
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
      setRunMessage(
        "The policy service could not be reached, so Dara is replaying the verified record without making a provider call.",
      );
    }
    demoEvents.forEach((event, index) => {
      timers.current.push(
        setTimeout(() => {
          setEvents((current) => [...current, event]);
          if (index === demoEvents.length - 1) setRunState("done");
        }, replayDelay(demoRun, index)),
      );
    });
  }

  function selectSeed(next: string) {
    timers.current.forEach(clearTimeout);
    eventSource.current?.close();
    const run = demoCorpus.runs.find((item) => item.seed_id === next);
    setSeedId(next);
    setLiveRun(null);
    setRunMessage("");
    setRunState("done");
    if (run) {
      setPrompt(run.brief);
      setEvents(seededEvents(run));
    }
  }

  function approve() {
    setToast("Already approved · trusted published hash is on record");
    setTimeout(() => setToast(""), 2200);
  }

  const running = runState === "running";
  const live = runMode === "live";
  const phases = derivePhases(
    events.map((event) => event.kind),
    running,
  );
  const started = events.length > 0;
  const blockedRun = events.some((event) => event.kind === "policy.blocked");
  const assetUrl = live ? (liveRun?.asset_url ?? null) : demoRun.asset_url;
  const finished = runState === "done" && started;
  const activeEvent = events[events.length - 1];

  const summary = live
    ? {
        provider: "openai",
        model: "gpt-image-2",
        qa: liveRun?.qa_score,
        cost: liveRun?.actual_cost_usd ?? liveRun?.worst_case_cost_usd,
        attempts: liveRun?.qa_attempts,
      }
    : {
        provider: demoRun.provider,
        model: demoRun.model,
        qa: demoRun.qa_score,
        cost: demoRun.cost_usd,
        attempts: demoRun.qa_attempts,
      };

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      {/* Brief rail */}
      <div className="grid content-start gap-4 xl:sticky xl:top-8">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
            Generation control plane
          </p>
          <h1 className="text-3xl font-semibold leading-tight tracking-tighter text-ink">
            Make the work.
            <br />
            Keep the record.
          </h1>
          <p className="mt-3 text-sm leading-relaxed text-muted">
            Governed media pipelines with visible policy, honest cost, and
            provenance that survives the handoff.
          </p>
        </div>

        <Panel>
          <PanelHead
            title="New brief"
            trailing={
              <Badge
                dot
                tone={
                  blocked
                    ? "block"
                    : policyStatus === "live"
                      ? "allow"
                      : "warn"
                }
              >
                {blocked
                  ? "Pre-flight blocked"
                  : policyStatus === "live"
                    ? "Live policy active"
                    : policyStatus === "checking"
                      ? "Checking policy"
                      : "Demo policy preview"}
              </Badge>
            }
          />
          <PanelBody className="grid gap-5">
            <Field label="Run mode">
              <Segmented
                ariaLabel="Run mode"
                onChange={(next) => {
                  setRunMode(next);
                  eventSource.current?.close();
                  timers.current.forEach(clearTimeout);
                  setLiveRun(null);
                  setRunMessage("");
                  if (next === "demo") {
                    setVariants(3);
                    setEvents(demoEvents);
                    setRunState("done");
                  } else {
                    setVariants(1);
                    setEvents([]);
                    setRunState("ready");
                  }
                }}
                options={[
                  { value: "demo", label: "Demo replay · $0" },
                  { value: "live", label: "Live OpenAI · spends" },
                ]}
                value={runMode}
              />
              <p className="text-xs leading-relaxed text-subtle">
                {live ? (
                  "One candidate at a time, scored by OpenAI vision. Dara may revise up to three times inside the reserved cap."
                ) : (
                  <>
                    Defaulting to a clearly labelled deterministic fixture from{" "}
                    {demoCorpus.runs.length} committed seed runs. Production
                    proofs and fixtures are never conflated; live generation
                    requires the separate control above.
                  </>
                )}
              </p>
            </Field>

            {!live ? (
              <Field htmlFor="fixture" label="Replay fixture">
                <Select
                  id="fixture"
                  onChange={(event) => selectSeed(event.target.value)}
                  value={seedId}
                >
                  {demoCorpus.runs.map((run) => (
                    <option key={run.seed_id} value={run.seed_id}>
                      {run.title}
                    </option>
                  ))}
                </Select>
              </Field>
            ) : null}

            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              <Field htmlFor="project" label="Project">
                <Select defaultValue="northwind" id="project">
                  <option value="northwind">Northwind — Q3 campaign</option>
                  <option value="atlas">Atlas Hotels — Brand film</option>
                  <option value="field">Field Notes — Product launch</option>
                </Select>
              </Field>
              <Field htmlFor="policy" label="Policy">
                <Select
                  id="policy"
                  onChange={(event) => setPolicy(event.target.value)}
                  value={policy}
                >
                  <option value="permissive">Permissive</option>
                  <option value="standard">Standard client work</option>
                  <option value="locked">Locked demo · $0.02 max</option>
                </Select>
              </Field>
            </div>

            <Field htmlFor="prompt" label="Prompt">
              <Textarea
                id="prompt"
                onChange={(event) => setPrompt(event.target.value)}
                value={prompt}
              />
            </Field>

            <Field label="Aspect ratio">
              <Segmented
                ariaLabel="Aspect ratio"
                onChange={setAspectRatio}
                options={[
                  { value: "1:1", label: "1:1" },
                  { value: "3:2", label: "3:2" },
                  { value: "2:3", label: "2:3" },
                ]}
                value={aspectRatio}
              />
            </Field>

            <Field htmlFor="variants" label={`Variants · ${variants}`}>
              <input
                className="w-full accent-accent"
                disabled={live}
                id="variants"
                max={live ? 1 : 4}
                min={1}
                onChange={(event) => setVariants(Number(event.target.value))}
                type="range"
                value={variants}
              />
            </Field>
          </PanelBody>
        </Panel>

        {/* Pre-flight: the estimate is the point of decision, so it stays visible. */}
        <Panel className={cn(blocked && "border-blocked/30")}>
          <PanelBody className="grid gap-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Pre-flight estimate
                </p>
                <p className="mt-1 text-xs text-subtle">
                  Expected / three-attempt reserve ·{" "}
                  {policyStatus === "live" ? "from Dara API" : "local preview"}
                </p>
              </div>
              <p className="shrink-0 font-mono text-lg text-ink">
                ${formatSpend(estimate)}{" "}
                <span className="text-subtle">/ ${formatSpend(worstCase)}</span>
              </p>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-line">
              <div
                className={cn(
                  "h-full rounded-full transition-all",
                  blocked ? "bg-blocked" : "bg-verified",
                )}
                style={{ width: `${Math.min(100, (worstCase / 0.12) * 100)}%` }}
              />
            </div>
            {blocked ? (
              <StatusBlock icon={ShieldCheck} title="Blocked before spend" tone="block">
                {violationMessage} No provider will be called.
              </StatusBlock>
            ) : null}
            {runMessage ? (
              <p className="text-xs leading-relaxed text-pending-ink" role="status">
                {runMessage}
              </p>
            ) : null}
            <Button
              disabled={blocked || !prompt.trim()}
              full
              onClick={() => void runBrief()}
              size="lg"
            >
              {blocked
                ? "Blocked before spend"
                : running
                  ? live
                    ? "Generating with OpenAI…"
                    : "Replay in progress…"
                  : live
                    ? "Generate one live image"
                    : "Run verified demo"}
            </Button>
          </PanelBody>
        </Panel>
      </div>

      {/* Stage */}
      <Panel className="self-start">
        <PanelHead
          title={
            <div className="min-w-0 py-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                {live ? "Live still · OpenAI to B2" : demoRun.pipeline_id}
              </p>
              <h2 className="mt-1 truncate text-base font-semibold text-ink">
                {live ? "New live run" : demoRun.title}
              </h2>
            </div>
          }
          trailing={
            <Badge
              dot
              pulse={running}
              tone={
                blockedRun
                  ? "block"
                  : running
                    ? "warn"
                    : finished
                      ? "allow"
                      : "neutral"
              }
            >
              {blockedRun
                ? "Blocked"
                : running
                  ? "Running"
                  : finished
                    ? "Sealed"
                    : "Ready"}
            </Badge>
          }
        />

        <PanelBody className="grid gap-6">
          <Stepper steps={phases} />

          <Stage
            assetUrl={assetUrl}
            blockedRun={blockedRun}
            pipelineId={live ? "still-campaign" : demoRun.pipeline_id}
            running={running}
            started={started}
          />

          {running ? <ActiveEvent event={activeEvent} /> : null}

          {!started && !running ? (
            <p className="text-sm leading-relaxed text-subtle">
              Pick a project and describe the shot. The estimate updates as you
              type.
            </p>
          ) : null}

          {finished ? (
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
              {[
                { label: "Provider", value: summary.provider },
                { label: "Model", value: summary.model },
                {
                  label: "Vision QA",
                  value:
                    summary.qa == null
                      ? "—"
                      : `${Math.round(Number(summary.qa) * 100)} / 100`,
                },
                { label: "Cost", value: `$${summary.cost ?? "0.000000"}` },
              ].map((item) => (
                <div className="grid gap-1 bg-inset px-4 py-3" key={item.label}>
                  <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                    {item.label}
                  </dt>
                  <dd className="truncate font-mono text-sm text-ink">
                    {item.value}
                  </dd>
                </div>
              ))}
            </dl>
          ) : null}

          <EventStream events={events} />

          {finished && !blockedRun ? (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-verified/25 bg-verified/10 p-4">
              <p className="text-sm leading-relaxed text-muted">
                <strong className="font-semibold text-verified-ink">
                  {live
                    ? "Live asset published."
                    : "The deterministic QA-revision fixture is ready."}
                </strong>
                <br />
                {live
                  ? `Vision QA passed in ${liveRun?.qa_attempts ?? 1} attempt${liveRun?.qa_attempts === 1 ? "" : "s"}; Genblaze manifest embedded and hashes recorded in B2.`
                  : "Two attempts and parent lineage are replayed without claiming a live provider call or settled spend."}
              </p>
              <div className="flex flex-wrap gap-2">
                {assetUrl ? (
                  <a
                    className="inline-flex h-9 items-center rounded-xl border border-line bg-surface px-3 text-xs font-semibold text-ink transition-colors hover:bg-inset"
                    href={assetUrl}
                    rel="noreferrer"
                    target="_blank"
                  >
                    Open asset
                  </a>
                ) : null}
                <Button onClick={approve} size="sm" variant="secondary">
                  <RotateCcw aria-hidden className="size-3.5" />
                  Approve
                </Button>
              </div>
            </div>
          ) : null}

          {/* Sharing needs a real job_id from the live run store, so it is
              offered only on a completed live run. */}
          {live && liveRun?.status === "succeeded" && liveRun.asset_id ? (
            <ShareAction assetId={liveRun.asset_id} jobId={liveRun.job_id} />
          ) : null}
        </PanelBody>
      </Panel>

      {toast ? (
        <div
          className="fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-xl bg-ink px-4 py-3 text-xs font-medium text-page shadow-lg"
          role="status"
        >
          {toast}
        </div>
      ) : null}
    </div>
  );
}
