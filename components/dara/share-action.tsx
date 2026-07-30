"use client";

import { Share2 } from "lucide-react";
import { useState } from "react";
import { z } from "zod";

import { Button, CopyRow, StatusBlock } from "../ui";

const shareCreatedSchema = z.object({
  token: z.string(),
  url: z.string(),
  expires_at: z.string(),
});

const errorSchema = z.object({
  error: z.object({ message: z.string() }),
});

/**
 * Issue a token-scoped client disclosure for a completed run.
 *
 * The API resolves shares from the live run store, so this needs a real
 * `job_id` — which only a finished live run has. That is why sharing lives on
 * the run rather than on a recorded asset page.
 */
export function ShareAction({
  assetId,
  jobId,
}: {
  assetId: string;
  jobId: string;
}) {
  const [state, setState] = useState<"idle" | "creating" | "done" | "error">(
    "idle",
  );
  const [share, setShare] = useState<z.infer<typeof shareCreatedSchema> | null>(
    null,
  );
  const [message, setMessage] = useState("");

  async function createShare() {
    setState("creating");
    setMessage("");
    try {
      const response = await fetch("/api/shares", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          asset_ids: [assetId],
          expires_in_days: 30,
        }),
      });
      const body: unknown = await response.json();
      if (!response.ok) {
        const parsed = errorSchema.safeParse(body);
        throw new Error(
          parsed.success
            ? parsed.data.error.message
            : "Dara could not issue a disclosure link.",
        );
      }
      setShare(shareCreatedSchema.parse(body));
      setState("done");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Dara could not issue a disclosure link.",
      );
      setState("error");
    }
  }

  if (state === "done" && share) {
    return (
      <StatusBlock icon={Share2} title="Disclosure link issued" tone="allow">
        <CopyRow label="Client link" value={share.url} />
        <p className="mt-3 text-xs text-subtle">
          Expires{" "}
          {new Date(share.expires_at).toLocaleDateString("en-GB", {
            timeZone: "UTC",
          })}
          . The brief and parameters are withheld by policy.
        </p>
      </StatusBlock>
    );
  }

  return (
    <div className="grid gap-3">
      <Button
        disabled={state === "creating"}
        onClick={() => void createShare()}
        size="sm"
        variant="secondary"
      >
        <Share2 aria-hidden className="size-3.5" />
        {state === "creating" ? "Issuing…" : "Create client disclosure"}
      </Button>
      {state === "error" ? (
        <p className="text-xs leading-relaxed text-pending-ink" role="status">
          {message}
        </p>
      ) : null}
    </div>
  );
}
