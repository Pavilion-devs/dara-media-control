"use client";

import { LoaderCircle, RotateCcw } from "lucide-react";
import { useEffect, useState } from "react";

import {
  liveRunSchema,
  regenerationDiffSchema,
  type LiveRun,
  type RegenerationDiff,
} from "@/app/run-schema";
import { DataTable } from "@/components/dara/data-table";
import { Badge, Button, Panel, PanelBody, PanelHead } from "@/components/ui";

function errorMessage(payload: unknown, fallback: string) {
  if (
    typeof payload === "object"
    && payload !== null
    && "error" in payload
    && typeof payload.error === "object"
    && payload.error !== null
    && "message" in payload.error
    && typeof payload.error.message === "string"
  ) {
    return payload.error.message;
  }
  return fallback;
}

async function responseJson(response: Response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

export function RegenerationDiffView({ diff }: { diff: RegenerationDiff }) {
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Regeneration comparison</p>
          <p className="mt-1 text-xs leading-relaxed text-subtle">
            Same recorded conditions, new child run. Identical output bytes are
            not promised.
          </p>
        </div>
        <Badge dot tone={diff.lineage_verified ? "allow" : "block"}>
          {diff.lineage_verified ? "Lineage verified" : "Lineage mismatch"}
        </Badge>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {[
          { label: "Original", run: diff.original },
          { label: "Regenerated", run: diff.regenerated },
        ].map(({ label, run }) => (
          <Panel key={label}>
            <PanelHead
              title={label}
              trailing={<Badge tone={run.status === "succeeded" ? "allow" : "warn"}>{run.status}</Badge>}
            />
            <PanelBody className="grid gap-3">
              {run.asset_url ? (
                <img
                  alt={`${label} regeneration output`}
                  className="aspect-square w-full rounded-xl border border-line bg-inset object-cover"
                  src={run.asset_url}
                />
              ) : (
                <div className="flex aspect-square items-center justify-center rounded-xl border border-line bg-inset text-xs text-subtle">
                  No previewable asset
                </div>
              )}
              <dl className="grid gap-2 font-mono text-[11px]">
                <div className="flex justify-between gap-3">
                  <dt className="text-subtle">Job</dt>
                  <dd className="truncate text-ink">{run.job_id}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-subtle">Published hash</dt>
                  <dd className="truncate text-ink">
                    {run.published_sha256
                      ? `${run.published_sha256.slice(0, 8)}…${run.published_sha256.slice(-8)}`
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-subtle">Cost</dt>
                  <dd className="text-ink">
                    ${run.actual_cost_usd ?? run.expected_cost_usd}
                  </dd>
                </div>
              </dl>
            </PanelBody>
          </Panel>
        ))}
      </div>

      <Panel>
        <PanelHead title="Recorded parameter diff" />
        <DataTable
          columns={["parameter", "original", "regenerated", "match"]}
          rows={diff.parameters.map((parameter) => [
            parameter.name,
            parameter.original,
            parameter.regenerated,
            parameter.match,
          ])}
        />
      </Panel>

      <p className="text-xs leading-relaxed text-subtle">
        {diff.non_deterministic_note}
      </p>
    </div>
  );
}

export function RegenerationAction({
  relatedRun,
  run,
}: {
  relatedRun?: LiveRun;
  run: LiveRun;
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [child, setChild] = useState<LiveRun | null>(null);
  const [diff, setDiff] = useState<RegenerationDiff | null>(null);

  const existingChild =
    relatedRun?.parent_job_id === run.job_id ? relatedRun : undefined;
  const originalId = run.parent_job_id ?? run.job_id;
  const childId = run.parent_job_id ? run.job_id : existingChild?.job_id;

  useEffect(() => {
    if (!childId) return;
    const controller = new AbortController();
    void fetch(
      `/api/runs/${encodeURIComponent(childId)}/diff?against=${encodeURIComponent(originalId)}`,
      { cache: "no-store", signal: controller.signal },
    )
      .then(async (response) => {
        if (!response.ok) return;
        setDiff(regenerationDiffSchema.parse(await response.json()));
      })
      .catch((caught: unknown) => {
        if (caught instanceof DOMException && caught.name === "AbortError") return;
      });
    return () => controller.abort();
  }, [childId, originalId]);

  async function loadDiff(regenerated: LiveRun) {
    const response = await fetch(
      `/api/runs/${encodeURIComponent(regenerated.job_id)}/diff?against=${encodeURIComponent(run.job_id)}`,
      { cache: "no-store" },
    );
    const payload = await responseJson(response);
    if (!response.ok) {
      throw new Error(errorMessage(payload, "The regeneration diff is unavailable."));
    }
    setDiff(regenerationDiffSchema.parse(payload));
  }

  async function regenerate() {
    if (!armed) {
      setArmed(true);
      return;
    }
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/api/runs/${encodeURIComponent(run.job_id)}/regenerate`,
        { method: "POST" },
      );
      const payload = await responseJson(response);
      if (!response.ok) {
        throw new Error(errorMessage(payload, "Regeneration could not start."));
      }
      let current = liveRunSchema.parse(payload);
      setChild(current);

      for (let attempt = 0; attempt < 90; attempt += 1) {
        if (["succeeded", "failed", "blocked", "cancelled"].includes(current.status)) break;
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const poll = await fetch(
          `/api/runs/${encodeURIComponent(current.job_id)}`,
          { cache: "no-store" },
        );
        const nextPayload = await responseJson(poll);
        if (!poll.ok) {
          throw new Error(errorMessage(nextPayload, "The child run could not be read."));
        }
        current = liveRunSchema.parse(nextPayload);
        setChild(current);
      }

      if (current.status !== "succeeded") {
        throw new Error(
          current.error_message
          ?? `The child run ended with status ${current.status}.`,
        );
      }
      await loadDiff(current);
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : "Regeneration failed.");
    } finally {
      setBusy(false);
      setArmed(false);
    }
  }

  if (diff) return <RegenerationDiffView diff={diff} />;

  return (
    <div className="grid gap-3 rounded-xl border border-line bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-ink">Regenerate from manifest</p>
          <p className="mt-1 text-xs leading-relaxed text-subtle">
            Reconstructs the recorded parameters and creates a linked child run.
            This is a live provider action.
          </p>
        </div>
        <Button
          disabled={busy}
          onClick={() => void regenerate()}
          size="sm"
          variant={armed ? "accent" : "secondary"}
        >
          {busy ? (
            <LoaderCircle aria-hidden className="size-3.5 animate-spin" />
          ) : (
            <RotateCcw aria-hidden className="size-3.5" />
          )}
          {busy
            ? child
              ? `Running ${child.job_id.slice(0, 12)}…`
              : "Starting…"
            : armed
              ? `Confirm · reserve $${run.worst_case_cost_usd}`
              : "Regenerate · spends"}
        </Button>
      </div>
      {armed && !busy ? (
        <p className="text-xs leading-relaxed text-pending-ink" role="status">
          Click confirm to authorize provider spend. Policy and the durable daily
          cap are re-evaluated before the call.
        </p>
      ) : null}
      {error ? (
        <p className="text-xs leading-relaxed text-blocked-ink" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}
