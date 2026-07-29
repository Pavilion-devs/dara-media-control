import { z } from "zod";

export const ledgerSummarySchema = z.object({
  run_count: z.number().int().nonnegative(),
  approved_assets: z.number().int().nonnegative(),
  total_spend_usd: z.string(),
  cost_per_approved_asset_usd: z.string(),
  waste_ratio: z.string(),
  spend_prevented_usd: z.string(),
  generated_at: z.string(),
});

const cellSchema = z.union([z.string(), z.number(), z.boolean(), z.null()]);

export const ledgerQuerySchema = z.object({
  query: z.string(),
  columns: z.array(z.string()),
  rows: z.array(z.array(cellSchema)),
  generated_at: z.string(),
});

export const ledgerDashboardSchema = z.object({
  summary: ledgerSummarySchema,
  models: ledgerQuerySchema,
  projects: ledgerQuerySchema,
  months: ledgerQuerySchema,
});

export type LedgerSummary = z.infer<typeof ledgerSummarySchema>;
export type LedgerQuery = z.infer<typeof ledgerQuerySchema>;
export type LedgerDashboard = z.infer<typeof ledgerDashboardSchema>;
