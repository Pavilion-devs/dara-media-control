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

function seeded(
  overrides: Pick<Policy, "policy_id" | "name" | "description"> &
    Partial<Policy>,
): Policy {
  return {
    schema_version: 1,
    tenant_id: "demo",
    allowed_providers: ["openai", "replicate"],
    denied_providers: [],
    allowed_models: ["*"],
    denied_models: [],
    allowed_modalities: ["image"],
    allowed_aspect_ratios: ["1:1", "2:3", "3:2"],
    max_steps: 6,
    max_variants: 4,
    max_attempts: 3,
    max_duration_s: "10.000000",
    max_cost_usd_per_step: "0.500000",
    max_cost_usd_per_day: "1.000000",
    estimate_overrun_tolerance: "0.250000",
    min_qa_score: 0.75,
    require_qa: true,
    block_on_qa_failure: false,
    require_approval: true,
    embed_manifest: true,
    redact_prompt_on_share: true,
    strip_params_on_share: true,
    asset_retention_days: 365,
    manifest_retention_days: 2555,
    max_cost_usd_per_run: "2.000000",
    ...overrides,
  };
}

/**
 * The three policies committed in api/dara/main.py. Shown only when the live
 * policy engine cannot be reached, and labelled as such — the values are copied
 * from the source, not invented.
 */
export const seededPolicies: Policy[] = [
  seeded({
    policy_id: "pol_permissive",
    name: "Permissive",
    description: "High budgets with advisory QA for unrestricted exploration.",
    max_cost_usd_per_run: "20.000000",
    max_cost_usd_per_day: "100.000000",
    require_approval: false,
  }),
  seeded({
    policy_id: "pol_standard",
    name: "Standard",
    description: "Default guardrails for billable client work.",
    max_cost_usd_per_run: "2.000000",
    max_cost_usd_per_day: "1.000000",
  }),
  seeded({
    policy_id: "pol_locked",
    name: "Locked down",
    description: "Strict image-only controls with blocking QA.",
    max_cost_usd_per_run: "0.020000",
    max_cost_usd_per_day: "1.000000",
    allowed_aspect_ratios: ["1:1"],
    block_on_qa_failure: true,
  }),
];

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
