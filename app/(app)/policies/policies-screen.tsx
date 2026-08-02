"use client";

import { Ban, Check, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge, EmptyState, Panel, PanelBody, PanelHead, cn } from "@/components/ui";

import {
  enforcementPoints,
  policyListSchema,
  type Policy,
} from "../../policy-schema";

function money(value: string) {
  return `$${Number(value).toFixed(Number(value) < 1 ? 4 : 2)}`;
}

function Chips({ values, tone }: { values: string[]; tone: "allow" | "block" }) {
  if (values.length === 0) {
    return <span className="text-xs text-faint">none</span>;
  }
  return (
    <span className="flex flex-wrap gap-1.5">
      {values.map((value) => (
        <span
          className={cn(
            "rounded-full px-2 py-0.5 font-mono text-[11px]",
            tone === "allow"
              ? "bg-verified/10 text-verified-ink"
              : "bg-blocked/10 text-blocked-ink",
          )}
          key={value}
        >
          {value}
        </span>
      ))}
    </span>
  );
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line py-3 last:border-0">
      <dt className="text-xs text-subtle">{label}</dt>
      <dd className="text-right font-mono text-sm text-ink">{children}</dd>
    </div>
  );
}

function Flag({ on, children }: { on: boolean; children: React.ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 text-sm",
        on ? "text-verified-ink" : "text-subtle",
      )}
    >
      {on ? (
        <Check aria-hidden className="size-3.5" strokeWidth={2.5} />
      ) : (
        <Ban aria-hidden className="size-3.5" />
      )}
      {children}
    </span>
  );
}

export function PoliciesScreen() {
  const [policies, setPolicies] = useState<Policy[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [source, setSource] = useState<"loading" | "live" | "unavailable">("loading");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch("/api/policies", {
          signal: controller.signal,
        });
        if (!response.ok) throw new Error("Policy list unavailable");
        const parsed = policyListSchema.parse(await response.json());
        setPolicies(parsed.items);
        setSelectedId(
          parsed.items.find((policy) => policy.policy_id === "pol_standard")?.policy_id
          ?? parsed.items[0]?.policy_id
          ?? "",
        );
        setSource("live");
      } catch (error) {
        if ((error as Error).name === "AbortError") return;
        setSource("unavailable");
      }
    }
    void load();
    return () => controller.abort();
  }, []);

  const selected =
    policies.find((policy) => policy.policy_id === selectedId) ?? policies[0];

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
            Governance
          </p>
          <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
            Stop it before the money.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            A policy is a document attached to a project. It is enforced at four
            points — the first of them before any provider is called.
          </p>
        </div>
        <Badge dot tone={source === "live" ? "allow" : "warn"}>
          {source === "live"
            ? "Live policy engine"
            : source === "loading"
              ? "Loading policies"
              : "Policy engine unavailable"}
        </Badge>
      </div>

      {/* The four enforcement points, which is the part nobody else has. */}
      <Panel>
        <PanelHead
          title="Enforcement points"
          trailing={
            <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
              4 checks per run
            </span>
          }
        />
        <div className="grid gap-px bg-line md:grid-cols-2 xl:grid-cols-4">
          {enforcementPoints.map((point, index) => (
            <div className="grid gap-2 bg-surface p-5" key={point.key}>
              <div className="flex items-center gap-2">
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                    index === 0
                      ? "bg-accent text-accent-contrast"
                      : "bg-inset text-subtle",
                  )}
                >
                  {index + 1}
                </span>
                <span className="text-sm font-semibold text-ink">
                  {point.label}
                </span>
              </div>
              <p className="font-mono text-[11px] uppercase tracking-wider text-subtle">
                {point.summary}
              </p>
              <p className="text-xs leading-relaxed text-muted">
                {point.detail}
              </p>
            </div>
          ))}
        </div>
      </Panel>

      {source === "unavailable" ? (
        <EmptyState
          description="Dara could not read the active policy documents. No committed defaults have been substituted."
          icon={ShieldCheck}
          title="Policies unavailable"
        />
      ) : source === "loading" || !selected ? (
        <EmptyState
          description="Reading the active policy documents from Dara's B2-backed control plane."
          icon={ShieldCheck}
          title="Loading policies"
        />
      ) : (
      <div className="grid gap-6 xl:grid-cols-[300px_minmax(0,1fr)]">
        {/* Policy list */}
        <div className="grid content-start gap-3">
          {policies.map((policy) => {
            const active = policy.policy_id === selected.policy_id;
            return (
              <button
                aria-pressed={active}
                className={cn(
                  "rounded-2xl border p-4 text-left transition-colors",
                  active
                    ? "border-accent/40 bg-accent/10"
                    : "border-line bg-surface hover:bg-inset",
                )}
                key={policy.policy_id}
                onClick={() => setSelectedId(policy.policy_id)}
                type="button"
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">
                    {policy.name}
                  </span>
                  <span className="font-mono text-xs text-subtle">
                    {money(policy.max_cost_usd_per_run)}
                  </span>
                </span>
                <span className="mt-1 block font-mono text-[11px] text-subtle">
                  {policy.policy_id}
                </span>
                <span className="mt-2 block text-xs leading-relaxed text-muted">
                  {policy.description}
                </span>
              </button>
            );
          })}
        </div>

        {/* Selected policy */}
        <div className="grid content-start gap-6">
          <Panel>
            <PanelHead
              title={
                <div className="min-w-0 py-4">
                  <p className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                    {selected.policy_id}
                  </p>
                  <h2 className="mt-1 text-base font-semibold text-ink">
                    {selected.name}
                  </h2>
                </div>
              }
              trailing={
                <Badge tone={selected.block_on_qa_failure ? "block" : "neutral"}>
                  {selected.block_on_qa_failure ? "Blocking QA" : "Advisory QA"}
                </Badge>
              }
            />
            <PanelBody className="grid gap-6 md:grid-cols-2">
              <div>
                <p className="mb-2 flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  <ShieldCheck aria-hidden className="size-3.5" />
                  Budget
                </p>
                <dl className="grid">
                  <Row label="Per step">
                    {money(selected.max_cost_usd_per_step)}
                  </Row>
                  <Row label="Per run">
                    {money(selected.max_cost_usd_per_run)}
                  </Row>
                  <Row label="Per day">
                    {money(selected.max_cost_usd_per_day)}
                  </Row>
                  <Row label="Overrun tolerance">
                    {`${(Number(selected.estimate_overrun_tolerance) * 100).toFixed(0)}%`}
                  </Row>
                </dl>
              </div>

              <div>
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Shape
                </p>
                <dl className="grid">
                  <Row label="Max steps">{selected.max_steps}</Row>
                  <Row label="Max variants">{selected.max_variants}</Row>
                  <Row label="Max attempts">{selected.max_attempts}</Row>
                  <Row label="Max duration">{`${Number(selected.max_duration_s)}s`}</Row>
                </dl>
              </div>

              <div className="md:col-span-2">
                <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Providers and models
                </p>
                <dl className="grid gap-3">
                  <Row label="Allowed providers">
                    <Chips tone="allow" values={selected.allowed_providers} />
                  </Row>
                  <Row label="Denied providers">
                    <Chips tone="block" values={selected.denied_providers} />
                  </Row>
                  <Row label="Allowed models">
                    <Chips tone="allow" values={selected.allowed_models} />
                  </Row>
                  <Row label="Modalities">
                    <Chips tone="allow" values={selected.allowed_modalities} />
                  </Row>
                  <Row label="Aspect ratios">
                    <Chips
                      tone="allow"
                      values={selected.allowed_aspect_ratios}
                    />
                  </Row>
                </dl>
              </div>

              <div>
                <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Quality
                </p>
                <div className="grid gap-2">
                  <Row label="Minimum QA score">
                    {selected.min_qa_score.toFixed(2)}
                  </Row>
                  <Flag on={selected.require_qa}>QA required</Flag>
                  <Flag on={selected.block_on_qa_failure}>
                    Block on QA failure
                  </Flag>
                  <Flag on={selected.require_approval}>
                    Approval required before publish
                  </Flag>
                </div>
              </div>

              <div>
                <p className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Disclosure and retention
                </p>
                <div className="grid gap-2">
                  <Flag on={selected.embed_manifest}>Embed manifest</Flag>
                  <Flag on={selected.redact_prompt_on_share}>
                    Redact brief on share
                  </Flag>
                  <Flag on={selected.strip_params_on_share}>
                    Strip parameters on share
                  </Flag>
                  <Row label="Asset retention">
                    {`${selected.asset_retention_days}d`}
                  </Row>
                  <Row label="Manifest retention">
                    {`${selected.manifest_retention_days}d`}
                  </Row>
                </div>
              </div>
            </PanelBody>
          </Panel>

          <p className="text-xs leading-relaxed text-subtle">
            {source === "live"
              ? "Read from the live policy engine."
              : "The live policy engine is unreachable, so these are the defaults committed in the API. Values are copied from source, not invented."}{" "}
            Studio simulates the selected policy against your brief before
            anything is spent.
          </p>
        </div>
      </div>
      )}
    </div>
  );
}
