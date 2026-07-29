import { z } from "zod";

export const publicShareSchema = z.object({
  schema_version: z.literal(1),
  status: z.literal("active"),
  issued_at: z.string(),
  expires_at: z.string(),
  view_count: z.number().int().nonnegative(),
  assets: z
    .array(
      z.object({
        url: z.string(),
        mime_type: z.string(),
        shared_sha256: z.string().regex(/^[0-9a-f]{64}$/),
        verification: z.literal("record-matched"),
        provider: z.string(),
        model: z.string(),
        generated_at: z.string(),
      }),
    )
    .min(1),
  redaction: z.object({
    strip_prompt: z.literal(true),
    strip_params: z.literal(true),
    embed_mode: z.literal("pointer"),
  }),
  disclosure: z.string(),
  trust_note: z.string(),
});

export type PublicShare = z.infer<typeof publicShareSchema>;
