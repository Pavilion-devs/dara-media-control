import type { ReactNode } from "react";

import { cn } from "./cn";

/** Dara's semantic states. Colour never appears here for decoration. */
export type Tone = "allow" | "warn" | "block" | "accent" | "neutral";

const tones: Record<Tone, string> = {
  allow: "bg-verified/10 text-verified-ink",
  warn: "bg-pending/10 text-pending-ink",
  block: "bg-blocked/10 text-blocked-ink",
  accent: "bg-accent/10 text-accent-ink",
  neutral: "bg-inset text-subtle",
};

const dots: Record<Tone, string> = {
  allow: "bg-verified",
  warn: "bg-pending",
  block: "bg-blocked",
  accent: "bg-accent",
  neutral: "bg-faint",
};

export function Badge({
  tone = "neutral",
  dot = false,
  pulse = false,
  children,
  className,
}: {
  tone?: Tone;
  dot?: boolean;
  pulse?: boolean;
  children: ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1",
        "text-[10px] font-bold uppercase tracking-wider",
        tones[tone],
        className,
      )}
    >
      {dot ? (
        <span
          aria-hidden
          className={cn(
            "size-1.5 rounded-full",
            dots[tone],
            pulse && "animate-pulse",
          )}
        />
      ) : null}
      {children}
    </span>
  );
}
