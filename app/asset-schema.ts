import { z } from "zod";

import { verificationResponseSchema } from "./verification-schema";

export const assetRecordSchema = z.object({
  asset: z.object({
    asset_id: z.string(),
    run_id: z.string(),
    source_sha256: z.string(),
    published_sha256: z.string().nullable(),
    mime_type: z.string(),
    bytes: z.number().int().nonnegative(),
    source_content_address: z.string(),
    published_content_address: z.string().nullable(),
    modality: z.string(),
    manifest_embedded: z.boolean(),
    redacted: z.boolean(),
    qa_score: z.number().nullable(),
    approved: z.boolean(),
    cost_usd: z.string(),
    cost_basis: z.enum(["known", "estimated", "unknown"]),
  }),
  asset_url: z.string().url(),
  verification: verificationResponseSchema.nullable(),
});

export type AssetRecord = z.infer<typeof assetRecordSchema>;
