import { AlertTriangle, Check, Minus, X } from "lucide-react";

import type { VerificationResponse } from "@/app/verification-schema";
import { cn } from "../ui/cn";

type CheckTone = "pass" | "note" | "fail";

type CheckItem = {
  label: string;
  detail: string;
  tone: CheckTone;
};

/**
 * What Dara actually established, derived from the response rather than from
 * animated guesswork. A missing embedded manifest is a different discovery
 * path, not a failure, so it reads as a note.
 */
export function checksFor(result: VerificationResponse): CheckItem[] {
  const embedded = result.result === "embedded";
  const byHash = result.result === "matched-by-hash";

  return [
    {
      label: "File hashed locally",
      detail: "SHA-256 computed in your browser before anything was uploaded.",
      tone: "pass",
    },
    {
      label: embedded ? "Embedded manifest extracted" : "No embedded manifest",
      detail: embedded
        ? "A Genblaze manifest was found inside the file."
        : byHash
          ? "Dara resolved the file by its content hash instead."
          : "Nothing was embedded and no content-hash record was found.",
      tone: embedded ? "pass" : "note",
    },
    {
      label: "Canonical manifest integrity",
      detail: result.manifest
        ? result.manifest.hash_matches
          ? "The manifest's canonical hash verifies."
          : "The manifest's canonical hash does not verify."
        : "Not applicable without an embedded manifest.",
      tone: result.manifest
        ? result.manifest.hash_matches
          ? "pass"
          : "fail"
        : "note",
    },
    {
      label: "Trusted record match",
      detail:
        result.verification === "trusted-match"
          ? "The uploaded bytes match the published record held in B2."
          : result.verification === "trusted-mismatch"
            ? "A trusted record exists, but these bytes do not match it."
            : result.verification === "self-consistent"
              ? "Internally valid, but Dara holds no record of this file."
              : "No record of this file. It may have been generated elsewhere, or modified after generation.",
      tone:
        result.verification === "trusted-match"
          ? "pass"
          : result.verification === "trusted-mismatch"
            ? "fail"
            : "note",
    },
  ];
}

const marks: Record<CheckTone, { className: string; Icon: typeof Check }> = {
  pass: { className: "text-verified", Icon: Check },
  note: { className: "text-subtle", Icon: Minus },
  fail: { className: "text-blocked", Icon: X },
};

export function VerifyChecks({ items }: { items: CheckItem[] }) {
  return (
    <ul className="grid gap-3">
      {items.map((item) => {
        const mark = marks[item.tone];
        return (
          <li className="flex items-start gap-3" key={item.label}>
            <span
              className={cn(
                "mt-0.5 flex size-4 shrink-0 items-center justify-center",
                mark.className,
              )}
            >
              <mark.Icon aria-hidden className="size-4" strokeWidth={2.5} />
            </span>
            <span className="min-w-0">
              <span
                className={cn(
                  "block text-sm font-medium",
                  item.tone === "fail" ? "text-blocked-ink" : "text-ink",
                )}
              >
                {item.label}
              </span>
              <span className="block text-xs leading-relaxed text-subtle">
                {item.detail}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

/** Shown when trusted storage was unreachable but a manifest still parsed. */
export function StorageCaveat({ warning }: { warning: string }) {
  return (
    <p className="flex items-start gap-2 text-xs leading-relaxed text-pending-ink">
      <AlertTriangle aria-hidden className="mt-0.5 size-3.5 shrink-0" />
      {warning}
    </p>
  );
}
