"use client";

import { AudioLines, Ban, Clapperboard, ImageIcon, ShieldCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ActiveEvent, EventStream, type RunEvent } from "@/components/dara/event-stream";
import { derivePhases } from "@/components/dara/run-phases";
import { ShareAction } from "@/components/dara/share-action";
import { VersionTree, type VersionNode } from "@/components/dara/version-tree";
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

import { policyListSchema, type Policy } from "../../policy-schema";
import { projectListSchema, type Project } from "../../project-schema";
import { liveRunSchema, type LiveRun } from "../../run-schema";
import { apiErrorSchema } from "../../verification-schema";

type PolicySimulation = {
  estimate: { expected_usd: string; worst_case_usd: string };
  decision: {
    outcome: "allow" | "warn" | "block";
    violations: Array<{ code: string; message: string }>;
  };
};

type ConnectionState = "loading" | "live" | "unavailable";

function formatSpend(value: number | null) {
  if (value === null) return "—";
  return value < 0.1 ? value.toFixed(3) : value.toFixed(2);
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
            : event.type === "run.completed" || event.type === "publish.completed"
              ? "success"
              : "normal",
    } as RunEvent;
  });
}

const pipelineIcon: Record<string, typeof ImageIcon> = {
  "still-campaign": ImageIcon,
  "motion-spot": Clapperboard,
  "voiceover-pack": AudioLines,
};

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
          Nothing was spent. The policy decision is preserved in the live ledger.
        </p>
      </div>
    );
  }

  if (assetUrl && !running) {
    return (
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
            : "Your generated asset will appear here."}
      </p>
    </div>
  );
}

export function StudioScreen() {
  const [prompt, setPrompt] = useState("");
  const [aspectRatio, setAspectRatio] = useState("1:1");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [projectState, setProjectState] = useState<ConnectionState>("loading");
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [policyId, setPolicyId] = useState("");
  const [policyListState, setPolicyListState] = useState<ConnectionState>("loading");
  const [liveRun, setLiveRun] = useState<LiveRun | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [runState, setRunState] = useState<"ready" | "running" | "done">("ready");
  const simulationKey = `${policyId}:${aspectRatio}`;
  const [simulationResult, setSimulationResult] = useState<{
    key: string;
    value: PolicySimulation;
  } | null>(null);
  const simulation =
    simulationResult?.key === simulationKey ? simulationResult.value : null;
  const [policyStatus, setPolicyStatus] = useState<"checking" | "live" | "unavailable">(
    "checking",
  );
  const [runMessage, setRunMessage] = useState("");
  const [generationArmed, setGenerationArmed] = useState(false);
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);
  const eventSource = useRef<EventSource | null>(null);

  const estimate = simulation ? Number(simulation.estimate.expected_usd) : null;
  const worstCase = simulation ? Number(simulation.estimate.worst_case_usd) : null;
  const blocked = simulation?.decision.outcome === "block";
  const violationMessage =
    simulation?.decision.violations[0]?.message
    ?? "The active policy rejected this request. Nothing will be spent.";

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/projects", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Project list unavailable");
        const parsed = projectListSchema.parse(await response.json());
        setProjects(parsed.items);
        setProjectId((current) => current || parsed.items[0]?.project_id || "");
        setProjectState("live");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setProjectState("unavailable");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/policies", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Policy list unavailable");
        const parsed = policyListSchema.parse(await response.json());
        setPolicies(parsed.items);
        setPolicyId((current) =>
          current
          || parsed.items.find((policy) => policy.policy_id === "pol_standard")?.policy_id
          || parsed.items[0]?.policy_id
          || "",
        );
        setPolicyListState("live");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setPolicyListState("unavailable");
        setPolicyStatus("unavailable");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!policyId) return;
    const controller = new AbortController();
    const requestKey = `${policyId}:${aspectRatio}`;
    const timer = setTimeout(async () => {
      setPolicyStatus("checking");
      try {
        const response = await fetch(
          `/api/policies/${encodeURIComponent(policyId)}/simulate`,
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
              variants: 1,
              max_attempts: 3,
              step_count: 1,
              qa_enabled: true,
              prompt_expansion: true,
            }),
            signal: controller.signal,
          },
        );
        if (!response.ok) throw new Error("Policy preview unavailable");
        setSimulationResult({
          key: requestKey,
          value: (await response.json()) as PolicySimulation,
        });
        setPolicyStatus("live");
      } catch (error) {
        if ((error as Error).name !== "AbortError") setPolicyStatus("unavailable");
      }
    }, 180);

    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [aspectRatio, policyId]);

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
      setRunMessage("Generation completed and the durable B2 record was sealed.");
      return true;
    }
    if (["failed", "blocked", "cancelled"].includes(current.status)) {
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
    const stream = new EventSource(`/api/runs/${encodeURIComponent(jobId)}/events`);
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
    if (blocked || worstCase === null || policyStatus !== "live") return;
    if (!generationArmed) {
      setGenerationArmed(true);
      setRunMessage(
        `Dara will reserve at most $${formatSpend(worstCase)}. Confirm once more to call OpenAI.`,
      );
      return;
    }

    setGenerationArmed(false);
    timers.current.forEach(clearTimeout);
    eventSource.current?.close();
    eventSource.current = null;
    setEvents([]);
    setRunState("running");
    setRunMessage("");
    setLiveRun(null);

    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: projectId,
          policy_id: policyId,
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
            : "Dara could not start the OpenAI image job.",
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
          : "Dara could not start the OpenAI image job.",
      );
    }
  }

  async function cancelLiveRun() {
    if (!liveRun || runState !== "running") return;
    setRunMessage("Requesting cancellation…");
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(liveRun.job_id)}/cancel`,
        { method: "POST" },
      );
      const json: unknown = await response.json();
      if (!response.ok) {
        const parsed = apiErrorSchema.safeParse(json);
        throw new Error(
          parsed.success ? parsed.data.error.message : "Dara could not cancel this run.",
        );
      }
      eventSource.current?.close();
      applyLiveRun(liveRunSchema.parse(json));
    } catch (error) {
      setRunMessage(
        error instanceof Error ? error.message : "Dara could not cancel this run.",
      );
    }
  }

  const running = runState === "running";
  const phases = derivePhases(
    events.map((event) => event.kind),
    running,
  );
  const started = events.length > 0;
  const blockedRun = events.some((event) => event.kind === "policy.blocked");
  const assetUrl = liveRun?.asset_url ?? null;
  const finished = runState === "done" && started;
  const activeEvent = events[events.length - 1];
  const lastAttempt = liveRun?.attempts.at(-1);
  const versions: VersionNode[] = (liveRun?.attempts ?? []).map((attempt) => ({
    id: attempt.genblaze_run_id,
    parentId: attempt.parent_run_id,
    status: attempt.status,
    label: `Attempt ${attempt.attempt}`,
    prompt: attempt.prompt,
    provider: attempt.provider,
    model: attempt.model,
    qaScore: attempt.qa_score,
  }));
  const liveReady =
    projectState === "live"
    && policyListState === "live"
    && policyStatus === "live"
    && Boolean(projectId)
    && Boolean(policyId);

  return (
    <div className="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
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
            Dara checks policy before spend, generates through OpenAI and Genblaze,
            and stores the asset, provenance, attempts, and accounting in B2.
          </p>
        </div>

        <Panel>
          <PanelHead
            title="New generation"
            trailing={
              <Badge
                dot
                tone={blocked ? "block" : policyStatus === "live" ? "allow" : "warn"}
              >
                {blocked
                  ? "Pre-flight blocked"
                  : policyStatus === "live"
                    ? "Live policy active"
                    : policyStatus === "checking"
                      ? "Checking policy"
                      : "Policy unavailable"}
              </Badge>
            }
          />
          <PanelBody className="grid gap-5">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
              <Field htmlFor="project" label="Project">
                <Select
                  disabled={projectState !== "live" || projects.length === 0}
                  id="project"
                  onChange={(event) => {
                    setProjectId(event.target.value);
                    setGenerationArmed(false);
                  }}
                  value={projectId}
                >
                  {projects.length === 0 ? (
                    <option value="">
                      {projectState === "loading" ? "Loading projects…" : "Projects unavailable"}
                    </option>
                  ) : null}
                  {projects.map((project) => (
                    <option key={project.project_id} value={project.project_id}>
                      {project.name}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field htmlFor="policy" label="Policy">
                <Select
                  disabled={policyListState !== "live" || policies.length === 0}
                  id="policy"
                  onChange={(event) => {
                    setPolicyId(event.target.value);
                    setGenerationArmed(false);
                  }}
                  value={policyId}
                >
                  {policies.length === 0 ? (
                    <option value="">
                      {policyListState === "loading" ? "Loading policies…" : "Policies unavailable"}
                    </option>
                  ) : null}
                  {policies.map((policy) => (
                    <option key={policy.policy_id} value={policy.policy_id}>
                      {policy.name}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field htmlFor="prompt" label="Prompt">
              <Textarea
                id="prompt"
                onChange={(event) => {
                  setPrompt(event.target.value);
                  setGenerationArmed(false);
                }}
                placeholder="Describe the image you want Dara to generate."
                value={prompt}
              />
            </Field>

            <Field label="Aspect ratio">
              <Segmented
                ariaLabel="Aspect ratio"
                onChange={(next) => {
                  setAspectRatio(next);
                  setGenerationArmed(false);
                }}
                options={[
                  { value: "1:1", label: "1:1" },
                  { value: "3:2", label: "3:2" },
                  { value: "2:3", label: "2:3" },
                ]}
                value={aspectRatio}
              />
            </Field>
          </PanelBody>
        </Panel>

        <Panel className={cn(blocked && "border-blocked/30")}>
          <PanelBody className="grid gap-4">
            <div className="flex items-end justify-between gap-4">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Live pre-flight estimate
                </p>
                <p className="mt-1 text-xs text-subtle">
                  Expected / three-attempt reserve · active model registry
                </p>
              </div>
              <p className="shrink-0 font-mono text-lg text-ink">
                {estimate === null ? "—" : `$${formatSpend(estimate)}`} {" "}
                <span className="text-subtle">
                  / {worstCase === null ? "—" : `$${formatSpend(worstCase)}`}
                </span>
              </p>
            </div>
            {worstCase !== null ? (
              <div className="h-1.5 overflow-hidden rounded-full bg-line">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    blocked ? "bg-blocked" : "bg-verified",
                  )}
                  style={{ width: `${Math.min(100, (worstCase / 0.12) * 100)}%` }}
                />
              </div>
            ) : null}
            {blocked ? (
              <StatusBlock icon={ShieldCheck} title="Blocked before spend" tone="block">
                {violationMessage} No provider will be called.
              </StatusBlock>
            ) : null}
            {!liveReady && policyStatus === "unavailable" ? (
              <StatusBlock icon={ShieldCheck} title="Live control plane unavailable" tone="warn">
                Dara will not substitute recorded data or start generation until the live
                policy service is reachable.
              </StatusBlock>
            ) : null}
            {runMessage ? (
              <p className="text-xs leading-relaxed text-pending-ink" role="status">
                {runMessage}
              </p>
            ) : null}
            <Button
              disabled={blocked || !prompt.trim() || running || !liveReady}
              full
              onClick={() => void runBrief()}
              size="lg"
            >
              {blocked
                ? "Blocked before spend"
                : running
                  ? "Generating with OpenAI…"
                  : generationArmed
                    ? `Confirm generation · up to $${formatSpend(worstCase)}`
                    : "Generate with OpenAI"}
            </Button>
            <p className="text-center text-[11px] leading-relaxed text-subtle">
              The first click reveals the live maximum. The second authorizes the provider call.
            </p>
            {running && liveRun ? (
              <Button full onClick={() => void cancelLiveRun()} variant="secondary">
                Cancel run
              </Button>
            ) : null}
          </PanelBody>
        </Panel>
      </div>

      <Panel className="self-start">
        <PanelHead
          title={
            <div className="min-w-0 py-4">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                Live still · OpenAI → Genblaze → B2
              </p>
              <h2 className="mt-1 truncate text-base font-semibold text-ink">
                {liveRun ? liveRun.job_id : "New generation"}
              </h2>
            </div>
          }
          trailing={
            <Badge
              dot
              pulse={running}
              tone={blockedRun ? "block" : running ? "warn" : finished ? "allow" : "neutral"}
            >
              {blockedRun ? "Blocked" : running ? "Running" : finished ? "Sealed" : "Ready"}
            </Badge>
          }
        />

        <PanelBody className="grid gap-6">
          <Stepper steps={phases} />
          <Stage
            assetUrl={assetUrl}
            blockedRun={blockedRun}
            pipelineId={liveRun?.pipeline_id ?? "still-campaign"}
            running={running}
            started={started}
          />
          {running ? <ActiveEvent event={activeEvent} /> : null}
          {!started && !running ? (
            <p className="text-sm leading-relaxed text-subtle">
              Choose a live project, enter a prompt, review the policy reservation,
              and authorize the generation. No recorded run is preloaded here.
            </p>
          ) : null}

          {finished && liveRun ? (
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
              {[
                { label: "Provider", value: lastAttempt?.provider ?? "—" },
                { label: "Model", value: lastAttempt?.model ?? "—" },
                {
                  label: "Vision QA",
                  value: liveRun.qa_score == null ? "—" : `${liveRun.qa_score.toFixed(2)} / 1.00`,
                },
                {
                  label: "Cost",
                  value: liveRun.actual_cost_usd ? `$${liveRun.actual_cost_usd}` : "—",
                },
              ].map((item) => (
                <div className="grid gap-1 bg-inset px-4 py-3" key={item.label}>
                  <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                    {item.label}
                  </dt>
                  <dd className="truncate font-mono text-sm text-ink">{item.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          <EventStream events={events} />

          {finished && versions.length ? (
            <div>
              <div className="mb-3 flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-ink">Version tree</p>
                <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                  {versions.length} recorded attempt{versions.length === 1 ? "" : "s"}
                </span>
              </div>
              <VersionTree nodes={versions} />
            </div>
          ) : null}

          {finished && liveRun?.status === "succeeded" ? (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-verified/25 bg-verified/10 p-4">
              <p className="text-sm leading-relaxed text-muted">
                <strong className="font-semibold text-verified-ink">
                  Live asset published.
                </strong>
                <br />
                Vision QA, the embedded Genblaze manifest, both hashes, and the final
                accounting record are stored in B2.
              </p>
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
            </div>
          ) : null}

          {liveRun?.status === "succeeded" && liveRun.asset_id ? (
            <ShareAction assetId={liveRun.asset_id} jobId={liveRun.job_id} />
          ) : null}
        </PanelBody>
      </Panel>
    </div>
  );
}
