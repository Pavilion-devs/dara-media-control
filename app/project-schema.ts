import { z } from "zod";

export const projectSchema = z.object({
  schema_version: z.number().int().positive(),
  project_id: z.string(),
  tenant_id: z.string(),
  name: z.string(),
  client: z.string(),
  policy_id: z.string(),
  created_at: z.string(),
  tags: z.array(z.string()),
});

export const projectListSchema = z.object({
  items: z.array(projectSchema),
});

export type Project = z.infer<typeof projectSchema>;
