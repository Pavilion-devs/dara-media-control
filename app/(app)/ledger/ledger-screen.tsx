"use client";

import { useEffect, useState } from "react";

import { DataTable } from "@/components/dara/data-table";
import { Badge, Panel, PanelHead, cn } from "@/components/ui";

import {
  ledgerDashboardSchema,
  type LedgerQuery,
  type LedgerSummary,
} from "../../ledger-schema";
import { recordedLedgerProof } from "../../ledger-proof";

type Dashboard = {
  summary: LedgerSummary;
  models: LedgerQuery;
  projects: LedgerQuery;
  months: LedgerQuery;
};

const clientProjectNames: Record<string, string> = {
  prj_northwind_q3: "Northwind — Q3 campaign",
  prj_atlas_brand: "Atlas Hotels — Brand film",
  prj_field_launch: "Field Notes — Product launch",
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
  // Seeded with the recorded proof so the page is populated on first paint
  // rather than flashing empty tables. The label starts as "recorded" and only
  // claims "live" once the B2 query actually answers, so what is shown always
  // matches what it says it is.
  const [live, setLive] = useState<Dashboard>(recordedLedgerProof);
  const [ledgerState, setLedgerState] = useState<"live" | "fallback">(
    "fallback",
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
        // The seeded recorded proof already stands; nothing to swap in.
        if ((error as Error).name === "AbortError") return;
      }
    }
    void loadLedger();
    return () => controller.abort();
  }, []);

  const summary = live.summary;
  const wastePercent =
    (Number(summary.waste_ratio) * 100).toFixed(1);
  const wasteSpend = Number(summary.total_spend_usd) * Number(summary.waste_ratio);
  const clientProjectRows = live.projects.rows
    .filter((row) => typeof row[0] === "string" && row[0] in clientProjectNames)
    .map((row) => [clientProjectNames[String(row[0])], ...row.slice(1)]);
  const clientProjectColumns = ["project", ...live.projects.columns.slice(1)];

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
        <Badge dot tone={ledgerState === "live" ? "allow" : "warn"}>
          {ledgerState === "live"
            ? "Live · DuckDB over B2"
            : "Recorded proof"}
        </Badge>
      </div>

      {/* The three numbers the PRD says nobody else tracks. */}
      <div className="grid gap-4 md:grid-cols-3">
        <Metric
          detail={
            `Across ${summary.run_count} accounted runs, including discarded attempts.`
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
        {ledgerState === "live"
          ? `Generated ${new Date(summary.generated_at).toISOString()} · total spend $${summary.total_spend_usd}`
          : "Live ledger unavailable · verified B2 snapshot from 29 Jul 2026"}
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
            columns={clientProjectColumns}
            empty="No client-project spend is recorded yet. Internal probes stay out of this view."
            rows={clientProjectRows}
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
        Null cells are values the recorded evidence did not preserve; they are
        shown as unknown rather than filled in. Conservative low-quality policy
        reservations are used where a provider did not return settled cost.
      </p>
    </div>
  );
}
