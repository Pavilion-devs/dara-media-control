import { z } from "zod";

export const runEventSchema = z.object({
  seq: z.number().int().positive(),
  type: z.string(),
  at: z.string(),
  provider: z.string().nullable(),
  model: z.string().nullable(),
  message: z.string(),
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
  asset_url: z.string().url().nullable(),
  error_code: z.string().nullable(),
  error_message: z.string().nullable(),
});

export type LiveRun = z.infer<typeof liveRunSchema>;
