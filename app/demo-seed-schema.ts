import { z } from "zod";

export const demoSeedEventSchema = z.object({
  at_ms: z.number().int().nonnegative(),
  type: z.string(),
  provider: z.string(),
  model: z.string(),
  message: z.string(),
});

export const demoSeedRunSchema = z.object({
  seed_id: z.string(),
  evidence: z.enum(["production-proof", "deterministic-fixture"]),
  pipeline_id: z.enum([
    "still-campaign",
    "motion-spot",
    "voiceover-pack",
    "regenerate",
  ]),
  title: z.string(),
  project_id: z.string(),
  policy_id: z.string(),
  brief: z.string(),
  provider: z.string(),
  model: z.string(),
  outcome: z.enum(["succeeded", "failed", "blocked"]),
  approved: z.boolean(),
  qa_score: z.number().min(0).max(1).nullable(),
  qa_attempts: z.number().int().nonnegative(),
  cost_usd: z.string().regex(/^\d+\.\d{6}$/),
  saved_cost_usd: z.string().regex(/^\d+\.\d{6}$/),
  asset_url: z.string().nullable(),
  events: z.array(demoSeedEventSchema).min(1),
  voice: z.string().optional(),
  batch_index: z.number().int().nonnegative().optional(),
});

export const demoSeedCorpusSchema = z.object({
  schema_version: z.literal(1),
  generated_at: z.string(),
  default_seed_id: z.string(),
  runs: z.array(demoSeedRunSchema).min(12).max(15),
});

export type DemoSeedRun = z.infer<typeof demoSeedRunSchema>;
