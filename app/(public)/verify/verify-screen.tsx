"use client";

import { ArrowDown, RotateCcw, ShieldCheck } from "lucide-react";
import { useRef, useState } from "react";

import { HashDisplay } from "@/components/dara/hash-display";
import { LineageSpine, type LineageNode } from "@/components/dara/lineage-spine";
import {
  StorageCaveat,
  VerifyChecks,
  checksFor,
} from "@/components/dara/verify-checks";
import {
  Badge,
  Button,
  Panel,
  PanelBody,
  PanelHead,
  StatusBlock,
  Stepper,
  cn,
  type Step,
  type Tone,
} from "@/components/ui";

import {
  apiErrorSchema,
  type VerificationResponse,
  verificationResponseSchema,
} from "../../verification-schema";

/** All five states are designed; none is a dead end. */
const states: Record<
  VerificationResponse["verification"],
  { title: string; label: string; tone: Tone }
> = {
  "trusted-match": {
    title: "Trusted published record match",
    label: "Verified",
    tone: "allow",
  },
  "trusted-mismatch": {
    title: "Trusted record mismatch",
    label: "Changed",
    tone: "block",
  },
  "self-consistent": {
    title: "Internally consistent",
    label: "Untrusted",
    tone: "warn",
  },
  unknown: { title: "No trusted record", label: "Unknown", tone: "warn" },
};

type Phase = "idle" | "staged" | "checking" | "done" | "error";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

async function sha256Hex(file: File) {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    await file.arrayBuffer(),
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

function MetaStrip({ result }: { result: VerificationResponse }) {
  const items = [
    { label: "Discovery", value: result.result },
    { label: "Storage", value: result.storage_status },
    ...(result.manifest
      ? [
          {
            label: "Manifest",
            value: result.manifest.hash_matches ? "valid" : "invalid",
          },
        ]
      : []),
  ];

  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-3">
      {items.map((item) => (
        <div className="grid gap-1 bg-inset px-4 py-3" key={item.label}>
          <dt className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
            {item.label}
          </dt>
          <dd className="font-mono text-sm text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function VerifyScreen() {
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("");
  const [staged, setStaged] = useState<{
    file: File;
    sha256: string;
  } | null>(null);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState("");
  const [dragging, setDragging] = useState(false);

  /** Hash locally first — no network, so the claim is watched, not asserted. */
  async function stageFile(file?: File) {
    if (!file) return;
    setMessage("");
    setFileName(file.name);
    setPhase("staged");
    try {
      setStaged({ file, sha256: await sha256Hex(file) });
    } catch {
      setStaged(null);
      setMessage(
        "This browser would not hash the file locally. Verification needs a secure context.",
      );
      setPhase("error");
    }
  }

  async function verifyStaged() {
    if (!staged) return;
    setPhase("checking");
    setMessage("");
    const body = new FormData();
    body.set("file", staged.file);
    try {
      // Route through the Next handler so the API bearer token stays server-side.
      const response = await fetch("/api/verify", { method: "POST", body });
      // If an edge rejects a large upload before the route runs, fall back to
      // the local hash. Normal files must reach full inspection so an embedded
      // manifest is not mislabeled as a hash-only discovery.
      if (response.status === 413) {
        const lookupResponse = await fetch(`/api/verify/${staged.sha256}`, {
          cache: "no-store",
        });
        if (lookupResponse.ok) {
          setResult(
            verificationResponseSchema.parse(await lookupResponse.json()),
          );
          setPhase("done");
          return;
        }
        throw new Error(
          `This deployment will not accept a ${formatBytes(staged.file.size)} upload. The SHA-256 above was still computed locally and is correct.`,
        );
      }
      const responseText = await response.text();
      let json: unknown;
      try {
        json = JSON.parse(responseText);
      } catch {
        throw new Error(
          response.ok
            ? "Dara returned an unreadable verification response."
            : responseText || "Dara could not verify this file. Try again.",
        );
      }
      if (!response.ok) {
        const error = apiErrorSchema.parse(json);
        throw new Error(error.error.message);
      }
      setResult(verificationResponseSchema.parse(json));
      setPhase("done");
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Dara could not verify this file. Try again.",
      );
      setPhase("error");
    }
  }

  function reset() {
    setStaged(null);
    setResult(null);
    setFileName("");
    setPhase("idle");
    setMessage("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const current = result ? states[result.verification] : null;
  const steps: Step[] = [
    {
      key: "hash",
      label: "Hash locally",
      state: staged ? "done" : "current",
    },
    {
      key: "record",
      label: "Match trusted record",
      state: phase === "checking" ? "current" : phase === "done" ? "done" : "upcoming",
    },
  ];

  const lineage: LineageNode[] = (result?.lineage ?? []).map((item, index) => ({
    key: `${item.run_id}-${index}`,
    step: `${String(index + 1).padStart(2, "0")} · ${item.relationship}`,
    title: `${item.provider ?? "Parent run"} / ${item.model ?? "record"}`,
    detail: item.run_id,
    trailing: new Date(item.at).toLocaleDateString("en-US", {
      month: "short",
      day: "2-digit",
      year: "numeric",
    }),
  }));

  return (
    <div className="mx-auto w-full max-w-4xl px-6 pb-24 pt-14 md:px-8 md:pt-20">
      <header className="mb-10">
        <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-subtle">
          Public verification
        </p>
        <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
          Check where it came from.
        </h1>
        <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
          No generation provider is contacted. Dara checks the file against its
          trusted storage record.
        </p>
      </header>

      <input
        accept="image/*,video/*,audio/*"
        hidden
        onChange={(event) => void stageFile(event.target.files?.[0])}
        ref={inputRef}
        type="file"
      />

      {phase === "idle" ? (
        <button
          className={cn(
            "flex w-full flex-col items-center justify-center gap-4 rounded-2xl border-2 border-dashed px-6 py-14 text-center transition-colors",
            dragging
              ? "border-accent bg-accent/5"
              : "border-line bg-surface hover:border-accent/40 hover:bg-inset",
          )}
          onClick={() => inputRef.current?.click()}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void stageFile(event.dataTransfer.files[0]);
          }}
          type="button"
        >
          <span className="flex size-12 items-center justify-center rounded-full border border-line bg-inset text-muted">
            <ArrowDown aria-hidden className="size-5" />
          </span>
          <span className="block text-lg font-semibold text-ink md:text-xl">
            Drop a file to check where it came from
          </span>
          <span className="block text-sm text-subtle">
            or choose a file · PNG, JPG, MP4, WAV up to 100 MB
          </span>
        </button>
      ) : null}

      {/* Staged and checking share a frame so the hash stays put between them. */}
      {phase === "staged" || phase === "checking" ? (
        <Panel>
          <PanelHead
            title={
              <div className="min-w-0 py-4">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  {staged
                    ? `${formatBytes(staged.file.size)} · ${staged.file.type || "unknown type"}`
                    : "Reading file"}
                </p>
                <h2 className="mt-1 truncate text-base font-semibold text-ink">
                  {fileName}
                </h2>
              </div>
            }
            trailing={
              <Badge dot pulse={phase === "checking"} tone="accent">
                {phase === "checking" ? "Checking" : "Ready to verify"}
              </Badge>
            }
          />
          <PanelBody className="grid gap-6">
            <Stepper steps={steps} />

            {staged ? (
              <div className="grid gap-3">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  SHA-256 · computed in your browser
                </span>
                <HashDisplay value={staged.sha256} />
                <p className="text-xs leading-relaxed text-subtle">
                  Nothing has been uploaded yet. This is the hash of the bytes
                  you hold; verifying compares it with the record Dara keeps.
                </p>
              </div>
            ) : null}

            <div className="flex flex-wrap gap-3">
              <Button
                disabled={!staged || phase === "checking"}
                onClick={() => void verifyStaged()}
              >
                <ShieldCheck aria-hidden className="size-4" />
                {phase === "checking"
                  ? "Checking the trusted record…"
                  : "Verify this file"}
              </Button>
              <Button
                disabled={phase === "checking"}
                onClick={reset}
                variant="secondary"
              >
                Choose a different file
              </Button>
            </div>
          </PanelBody>
        </Panel>
      ) : null}

      {phase === "error" ? (
        <StatusBlock title="Service status" tone="warn">
          <p>{message}</p>
          {/* The local hash survives a failed lookup — it is the one thing that
              never depended on the network. */}
          {staged ? (
            <div className="mt-5 grid gap-3 border-t border-pending/25 pt-5">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                SHA-256 · computed in your browser
              </span>
              <HashDisplay value={staged.sha256} />
            </div>
          ) : null}
          <div className="mt-4 flex flex-wrap gap-3">
            <Button onClick={reset} size="sm" variant="secondary">
              Choose another file
            </Button>
            {staged ? (
              <Button
                onClick={() => void verifyStaged()}
                size="sm"
                variant="secondary"
              >
                Try again
              </Button>
            ) : null}
          </div>
        </StatusBlock>
      ) : null}

      {phase === "done" && result && current ? (
        <Panel
          className={cn(
            phase === "done"
              && result.verification === "trusted-mismatch"
              && "verify-mismatch",
          )}
        >
          <PanelHead
            title={
              <div className="min-w-0 py-4">
                <p className="truncate text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Uploaded file · {fileName}
                </p>
                <h2 className="mt-1 text-base font-semibold text-ink">
                  {current.title}
                </h2>
              </div>
            }
            trailing={
              <Badge dot tone={current.tone}>
                {current.label}
              </Badge>
            }
          />
          <PanelBody className="grid gap-6 p-5 md:p-6">
            <div className="grid gap-3">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                {result.verification === "trusted-mismatch"
                  ? "Uploaded SHA-256"
                  : "Published SHA-256 · whole file"}
              </span>
              <HashDisplay
                diffAgainst={result.expected_published_sha256}
                tone={
                  result.verified
                    ? "verified"
                    : result.verification === "trusted-mismatch"
                      ? "mismatch"
                      : "neutral"
                }
                value={result.uploaded_sha256}
              />
            </div>

            {/* On a mismatch the trusted value sits directly beneath, aligned
                character-for-character, so the divergence is obvious. */}
            {result.expected_published_sha256 &&
            result.expected_published_sha256 !== result.uploaded_sha256 ? (
              <div className="grid gap-3 border-t border-line pt-6">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Expected published SHA-256
                </span>
                <HashDisplay value={result.expected_published_sha256} />
              </div>
            ) : null}

            <div className="border-t border-line pt-6">
              <p className="mb-4 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                What Dara checked
              </p>
              <VerifyChecks items={checksFor(result)} />
              {result.warning ? (
                <div className="mt-4">
                  <StorageCaveat warning={result.warning} />
                </div>
              ) : null}
            </div>

            <MetaStrip result={result} />

            {result.manifest ? (
              <div className="border-t border-line pt-6">
                <p className="mb-4 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                  Recorded generation steps
                </p>
                <div className="grid gap-3">
                  {result.manifest.steps.map((step, index) => (
                    <div
                      className="grid gap-3 rounded-xl border border-line bg-inset p-4"
                      key={`${step.provider}-${step.model}-${index}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <p className="font-mono text-sm text-ink">
                          {step.provider ?? "unknown provider"} / {step.model}
                        </p>
                        <Badge tone="neutral">
                          {step.cost_usd ? `$${step.cost_usd}` : "cost unknown"}
                        </Badge>
                      </div>
                      <dl className="grid gap-2 text-xs sm:grid-cols-2">
                        <div>
                          <dt className="text-subtle">Modality</dt>
                          <dd className="font-mono text-ink">{step.modality}</dd>
                        </div>
                        <div>
                          <dt className="text-subtle">Parameters</dt>
                          <dd className="break-words font-mono text-ink">
                            {JSON.stringify(step.params)}
                          </dd>
                        </div>
                      </dl>
                      <div>
                        <p className="text-xs text-subtle">Recorded prompt</p>
                        <p className="mt-1 text-sm leading-relaxed text-muted">
                          {step.prompt ?? "Redacted or not recorded by the provider adapter."}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
                <p className="mt-4 font-mono text-xs text-subtle">
                  Parent run: {result.manifest.parent_run_id ?? "none"} · created {new Date(result.manifest.created_at).toISOString()}
                </p>
              </div>
            ) : null}

            <div className="border-t border-line pt-6">
              <p className="mb-5 text-[10px] font-semibold uppercase tracking-wider text-subtle">
                Lineage
              </p>
              <LineageSpine nodes={lineage} />
            </div>

            <p className="border-t border-line pt-5 text-xs leading-relaxed text-subtle">
              Trust boundary: {result.trust_note}
            </p>

            {phase === "done" ? (
              <Button
                className="justify-self-start"
                onClick={reset}
                size="sm"
                variant="secondary"
              >
                <RotateCcw aria-hidden className="size-3.5" />
                Check another file
              </Button>
            ) : null}
          </PanelBody>
        </Panel>
      ) : null}

    </div>
  );
}
