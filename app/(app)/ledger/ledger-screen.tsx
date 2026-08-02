"use client";

import { BarChart3 } from "lucide-react";
import { useEffect, useState } from "react";

import { DataTable } from "@/components/dara/data-table";
import { Badge, EmptyState, Panel, PanelHead, Select, cn } from "@/components/ui";

import {
  ledgerDashboardSchema,
  type LedgerQuery,
  type LedgerSummary,
} from "../../ledger-schema";
import { projectListSchema, type Project } from "../../project-schema";

type Dashboard = {
  summary: LedgerSummary;
  models: LedgerQuery;
  projects: LedgerQuery;
  months: LedgerQuery;
};

function Metric({
  label,
  value,
  detail,
  emphasis = false,
}: {
  label: string;
  value: string;
  detail: string;
  emphasis?: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border p-6",
        emphasis ? "border-accent/25 bg-accent/10" : "border-line bg-surface",
      )}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
        {label}
      </p>
      <p className="mt-4 font-mono text-4xl font-medium tracking-tighter text-ink md:text-5xl">
        {value}
      </p>
      <p className="mt-3 text-xs leading-relaxed text-subtle">{detail}</p>
    </div>
  );
}

export function LedgerScreen() {
  const [live, setLive] = useState<Dashboard | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [ledgerState, setLedgerState] = useState<"loading" | "live" | "unavailable">(
    "loading",
  );

  useEffect(() => {
    const controller = new AbortController();
    void fetch("/api/projects", { cache: "no-store", signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Project list unavailable");
        const parsed = projectListSchema.parse(await response.json());
        setProjects(parsed.items);
        setProjectId(parsed.items[0]?.project_id ?? "");
        if (parsed.items.length === 0) setLedgerState("unavailable");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setLedgerState("unavailable");
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (!projectId) return;
    const controller = new AbortController();
    async function loadLedger() {
      setLive(null);
      setLedgerState("loading");
      try {
        const response = await fetch(
          `/api/ledger/dashboard?project_id=${encodeURIComponent(projectId)}`,
          {
            signal: controller.signal,
          },
        );
        if (!response.ok) {
          throw new Error("Ledger unavailable");
        }
        setLive(ledgerDashboardSchema.parse(await response.json()));
        setLedgerState("live");
      } catch (error) {
        if ((error as Error).name === "AbortError") return;
        setLedgerState("unavailable");
      }
    }
    void loadLedger();
    return () => controller.abort();
  }, [projectId]);

  if (live === null) {
    return (
      <div className="grid gap-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
              Spend ledger
            </p>
            <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
              The honest numbers.
            </h1>
            <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
              Every attempt counts — including the work that never shipped.
            </p>
          </div>
          <div className="grid min-w-56 gap-2">
            <Badge dot tone="warn">
              {ledgerState === "loading" ? "Querying B2" : "Live ledger unavailable"}
            </Badge>
            {projects.length ? (
              <Select
                aria-label="Ledger project"
                onChange={(event) => setProjectId(event.target.value)}
                value={projectId}
              >
                {projects.map((project) => (
                  <option key={project.project_id} value={project.project_id}>
                    {project.name}
                  </option>
                ))}
              </Select>
            ) : null}
          </div>
        </div>
        <EmptyState
          description={
            ledgerState === "loading"
              ? "DuckDB is querying the immutable accounting Parquet in Backblaze B2."
              : "Dara could not query the live B2 ledger. No recorded snapshot has been substituted."
          }
          icon={BarChart3}
          title={ledgerState === "loading" ? "Loading live ledger" : "Ledger unavailable"}
        />
      </div>
    );
  }

  const summary = live.summary;
  const wastePercent =
    (Number(summary.waste_ratio) * 100).toFixed(1);
  const wasteSpend = Number(summary.total_spend_usd) * Number(summary.waste_ratio);

  return (
    <div className="grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-widest text-subtle">
            Spend ledger
          </p>
          <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
            The honest numbers.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            Every attempt counts — including the work that never shipped.
          </p>
        </div>
        <div className="grid min-w-56 gap-2">
          <Badge dot tone="allow">Live · DuckDB over B2</Badge>
          <Select
            aria-label="Ledger project"
            onChange={(event) => setProjectId(event.target.value)}
            value={projectId}
          >
            {projects.map((project) => (
              <option key={project.project_id} value={project.project_id}>
                {project.name}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {/* The three numbers the PRD says nobody else tracks. */}
      <div className="grid gap-4 md:grid-cols-3">
        <Metric
          detail={
            `Across ${summary.run_count} accounted project runs, including discarded attempts.`
          }
          emphasis
          label="Cost / approved asset"
          value={`$${Number(summary.cost_per_approved_asset_usd).toFixed(2)}`}
        />
        <Metric
          detail="Policy-blocked work · zero provider calls were made."
          label="Spend prevented"
          value={`$${Number(summary.spend_prevented_usd).toFixed(2)}`}
        />
        <Metric
          detail={`$${wasteSpend.toFixed(6)} of $${summary.total_spend_usd} settled spend.`}
          label="Spend on unapproved work"
          value={`$${wasteSpend.toFixed(2)}`}
        />
      </div>

      <p className="text-sm text-muted">
        Published outcome: {summary.approved_assets} of {summary.run_count} accounted
        attempts produced an approved asset. Unapproved-spend share: {wastePercent}%.
      </p>

      <p className="font-mono text-xs text-subtle">
        {`Generated ${new Date(summary.generated_at).toISOString()} · total spend $${summary.total_spend_usd}`}
      </p>

      <Panel>
        <PanelHead title="Spend by model" />
        <DataTable
          barColumn="total_usd"
          columns={live.models.columns ?? []}
          empty="No accounted runs yet."
          rows={live.models.rows ?? []}
        />
      </Panel>

      <div className="grid gap-6 xl:grid-cols-2">
        <Panel>
          <PanelHead title="Spend by project" />
          <DataTable
            columns={live.projects.columns}
            empty="No project spend is recorded yet."
            rows={live.projects.rows}
          />
        </Panel>
        <Panel>
          <PanelHead title="Spend by month" />
          <DataTable
            barColumn="total_usd"
            columns={live.months.columns ?? []}
            empty="No monthly spend recorded."
            rows={live.months.rows ?? []}
          />
        </Panel>
      </div>

      <p className="text-xs leading-relaxed text-subtle">
        Null cells are shown as unknown rather than filled in. Conservative policy
        reservations are used where a provider did not return settled cost.
      </p>
    </div>
  );
}
