import { z } from "zod";

/** Mirrors `Policy` in api/dara/policy/models.py. */
export const policySchema = z.object({
  schema_version: z.number().int(),
  policy_id: z.string(),
  tenant_id: z.string(),
  name: z.string(),
  description: z.string(),
  allowed_providers: z.array(z.string()),
  denied_providers: z.array(z.string()),
  allowed_models: z.array(z.string()),
  denied_models: z.array(z.string()),
  allowed_modalities: z.array(z.string()),
  allowed_aspect_ratios: z.array(z.string()),
  max_steps: z.number().int(),
  max_variants: z.number().int(),
  max_attempts: z.number().int(),
  max_duration_s: z.string(),
  max_cost_usd_per_step: z.string(),
  max_cost_usd_per_run: z.string(),
  max_cost_usd_per_day: z.string(),
  estimate_overrun_tolerance: z.string(),
  min_qa_score: z.number(),
  require_qa: z.boolean(),
  block_on_qa_failure: z.boolean(),
  require_approval: z.boolean(),
  embed_manifest: z.boolean(),
  redact_prompt_on_share: z.boolean(),
  strip_params_on_share: z.boolean(),
  asset_retention_days: z.number().int(),
  manifest_retention_days: z.number().int(),
});

export const policyListSchema = z.object({
  items: z.array(policySchema),
});

export type Policy = z.infer<typeof policySchema>;

/** The four points at which the engine evaluates a policy. */
export const enforcementPoints = [
  {
    key: "pre_flight",
    label: "Pre-flight",
    summary: "Before any provider is called",
    detail:
      "Cost is estimated from the model registry and compared with budget. Providers, models, modality, aspect ratio, step, variant and attempt limits are all checked. A run that would exceed budget is rejected at zero cost.",
    fields: [
      "max_cost_usd_per_run",
      "max_cost_usd_per_day",
      "allowed_providers",
      "allowed_modalities",
      "allowed_aspect_ratios",
      "max_steps",
      "max_variants",
      "max_attempts",
    ],
  },
  {
    key: "pre_step",
    label: "Pre-step",
    summary: "Before every provider step",
    detail:
      "Each step is re-checked against the per-step ceiling and the remaining run budget, so a fallback route cannot quietly overspend.",
    fields: ["max_cost_usd_per_step", "estimate_overrun_tolerance"],
  },
  {
    key: "post_step",
    label: "Post-step",
    summary: "After quality assurance",
    detail:
      "The vision QA score is compared with the required minimum. Whether a failure blocks or merely warns is itself part of the policy.",
    fields: ["min_qa_score", "require_qa", "block_on_qa_failure"],
  },
  {
    key: "pre_publish",
    label: "Pre-publish",
    summary: "After embedding, before delivery",
    detail:
      "Manifest embedding and share redaction are verified before anything reaches a client, so a disclosure cannot leak what policy withheld.",
    fields: [
      "embed_manifest",
      "redact_prompt_on_share",
      "strip_params_on_share",
      "require_approval",
    ],
  },
] as const;
