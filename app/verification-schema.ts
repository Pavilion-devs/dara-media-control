import { z } from "zod";

export const verifyStepSchema = z.object({
  provider: z.string().nullable(),
  model: z.string(),
  modality: z.string(),
  prompt: z.string().nullable(),
  params: z.record(z.string(), z.unknown()),
  cost_usd: z.string().nullable(),
});

export const lineageItemSchema = z.object({
  run_id: z.string(),
  at: z.string(),
  relationship: z.enum(["generated", "parent"]),
  provider: z.string().nullable().optional(),
  model: z.string().nullable().optional(),
});

export const verificationResponseSchema = z.object({
  result: z.enum(["embedded", "matched-by-hash", "unknown"]),
  verification: z.enum([
    "trusted-match",
    "trusted-mismatch",
    "self-consistent",
    "unknown",
  ]),
  storage_status: z.enum(["available", "unavailable"]),
  verified: z.boolean(),
  uploaded_sha256: z.string().regex(/^[0-9a-f]{64}$/),
  expected_published_sha256: z
    .string()
    .regex(/^[0-9a-f]{64}$/)
    .nullable()
    .optional(),
  manifest: z
    .object({
      canonical_hash: z.string(),
      hash_matches: z.boolean(),
      declared_hashes_match: z.boolean(),
      run_id: z.string(),
      created_at: z.string(),
      steps: z.array(verifyStepSchema),
      parent_run_id: z.string().nullable(),
      redacted: z.boolean(),
    })
    .nullable(),
  lineage: z.array(lineageItemSchema),
  warning: z.string().nullable().optional(),
  trust_note: z.string(),
});

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.record(z.string(), z.unknown()),
    request_id: z.string().nullable(),
  }),
});

export type VerificationResponse = z.infer<typeof verificationResponseSchema>;
