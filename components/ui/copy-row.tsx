"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "./cn";

/**
 * A machine-recorded value with a copy affordance — hashes, run ids, manifest
 * keys. Dara's content is mostly identifiers, so this earns its place.
 */
export function CopyRow({
  label,
  value,
  display,
  className,
}: {
  label?: string;
  value: string;
  display?: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard access can be denied; the value stays selectable by hand.
    }
  }

  return (
    <div className={cn("grid gap-1", className)}>
      {label ? (
        <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
          {label}
        </span>
      ) : null}
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-lg border border-line bg-inset px-3 py-2 font-mono text-xs text-muted">
          {display ?? value}
        </code>
        <button
          className="shrink-0 rounded-lg p-2 text-faint transition-colors hover:bg-inset hover:text-ink"
          onClick={() => void copy()}
          title={copied ? "Copied" : "Copy"}
          type="button"
        >
          {copied ? (
            <Check aria-hidden className="size-3.5 text-verified" />
          ) : (
            <Copy aria-hidden className="size-3.5" />
          )}
          <span className="sr-only">
            {copied ? "Copied" : `Copy ${label ?? "value"}`}
          </span>
        </button>
      </div>
    </div>
  );
}
