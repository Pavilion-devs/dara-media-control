import type { LedgerQuery, LedgerSummary } from "./ledger-schema";

/**
 * Last verified live DuckDB-over-B2 result, captured during T-42 deployment QA.
 *
 * This is a continuity snapshot, not a synthetic demo dataset. It is shown only
 * when the live ledger cannot be reached, and the UI labels it RECORDED PROOF.
 * Per-project spend was not preserved in the screenshot evidence, so those cells
 * remain null instead of inventing values.
 */
export const recordedLedgerProof: {
  summary: LedgerSummary;
  models: LedgerQuery;
  projects: LedgerQuery;
  months: LedgerQuery;
} = {
  summary: {
    run_count: 9,
    approved_assets: 6,
    total_spend_usd: "0.095000",
    cost_per_approved_asset_usd: "0.015833",
    waste_ratio: "0.000000",
    spend_prevented_usd: "0.015000",
    generated_at: "2026-07-29T20:29:40Z",
  },
  models: {
    query: "spend_by_model",
    columns: ["model", "provider", "runs", "total_usd", "mean_usd"],
    rows: [["gpt-image-2", "openai", 9, "0.095000", "0.013571"]],
    generated_at: "2026-07-29T20:29:40Z",
  },
  projects: {
    query: "spend_by_project",
    columns: ["project_id", "runs", "approved_assets", "total_usd"],
    rows: [
      ["prj_t24_proof", 2, 2, null],
      ["prj_dara_smoke", 2, 2, null],
      ["prj_dara_ledger_smoke", 1, 1, null],
      ["prj_dara_qa_smoke", 2, 1, null],
      ["prj_policy_proof", 1, 0, null],
      ["prj_recovery_probe", 1, 0, null],
    ],
    generated_at: "2026-07-29T20:29:40Z",
  },
  months: {
    query: "spend_by_month",
    columns: ["month", "runs", "total_usd"],
    rows: [["2026-07", 9, "0.095000"]],
    generated_at: "2026-07-29T20:29:40Z",
  },
};
