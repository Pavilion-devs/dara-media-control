import { z } from "zod";

export const runEventSchema = z.object({
  seq: z.number().int().positive(),
  type: z.string(),
  at: z.string(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  message: z.string(),
});

export const runAttemptSchema = z.object({
  attempt: z.number().int().positive(),
  genblaze_run_id: z.string(),
  parent_run_id: z.string().nullable(),
  status: z.enum(["running", "rejected", "approved", "failed"]),
  prompt: z.string().nullable(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  qa_score: z.number().min(0).max(1).nullable(),
  asset_id: z.string().nullable(),
  created_at: z.string(),
});

export const policyDecisionSchema = z.object({
  enforcement_point: z.string(),
  outcome: z.enum(["allow", "warn", "block"]),
  violations: z.array(
    z.object({
      code: z.string(),
      severity: z.enum(["allow", "warn", "block"]),
      message: z.string(),
      field: z.string().nullable(),
      actual: z.string().nullable(),
      limit: z.string().nullable(),
    }),
  ),
  evaluated_at: z.string(),
  estimated_cost_usd: z.string(),
  saved_cost_usd: z.string().nullable(),
});

export const liveRunSchema = z.object({
  job_id: z.string(),
  tenant_id: z.string(),
  project_id: z.string(),
  pipeline_id: z.literal("still-campaign"),
  mode: z.literal("live"),
  status: z.enum([
    "queued",
    "running",
    "publishing",
    "succeeded",
    "failed",
    "blocked",
  ]),
  prompt: z.string(),
  aspect_ratio: z.enum(["1:1", "3:2", "2:3"]),
  variants: z.number().int().positive(),
  policy_id: z.string(),
  expected_cost_usd: z.string(),
  worst_case_cost_usd: z.string(),
  actual_cost_usd: z.string().nullable(),
  cost_basis: z.enum(["known", "estimated", "unknown"]),
  created_at: z.string(),
  updated_at: z.string(),
  events: z.array(runEventSchema),
  genblaze_run_id: z.string().nullable(),
  asset_id: z.string().nullable(),
  manifest_hash: z.string().nullable(),
  source_sha256: z.string().nullable(),
  published_sha256: z.string().nullable(),
  published_content_address: z.string().nullable(),
  qa_status: z.enum(["not_run", "passed", "failed"]),
  qa_score: z.number().min(0).max(1).nullable(),
  qa_attempts: z.number().int().nonnegative(),
  qa_issues: z.array(z.string()),
  parent_job_id: z.string().nullable(),
  source_manifest_hash: z.string().nullable(),
  attempts: z.array(runAttemptSchema),
  policy_decisions: z.array(policyDecisionSchema),
  asset_url: z.string().url().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});

export const liveRunListSchema = z.object({
  items: z.array(liveRunSchema),
  next_cursor: z.string().nullable(),
});

export const regenerationDiffSchema = z.object({
  original: liveRunSchema,
  regenerated: liveRunSchema,
  parameters: z.array(
    z.object({
      name: z.string(),
      original: z.union([z.string(), z.number(), z.boolean()]).nullable(),
      regenerated: z.union([z.string(), z.number(), z.boolean()]).nullable(),
      match: z.boolean(),
    }),
  ),
  source_manifest_hash: z.string().nullable(),
  lineage_verified: z.boolean(),
  non_deterministic_note: z.string(),
});

export type LiveRun = z.infer<typeof liveRunSchema>;
export type LiveRunList = z.infer<typeof liveRunListSchema>;
export type RegenerationDiff = z.infer<typeof regenerationDiffSchema>;
