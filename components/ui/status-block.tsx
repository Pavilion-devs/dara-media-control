import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "./cn";
import type { Tone } from "./badge";

const surfaces: Record<Tone, string> = {
  allow: "border-verified/25 bg-verified/10",
  warn: "border-pending/25 bg-pending/10",
  block: "border-blocked/25 bg-blocked/10",
  accent: "border-accent/25 bg-accent/10",
  neutral: "border-line bg-inset",
};

const inks: Record<Tone, string> = {
  allow: "text-verified-ink",
  warn: "text-pending-ink",
  block: "text-blocked-ink",
  accent: "text-accent-ink",
  neutral: "text-ink",
};

/**
 * A tinted outcome panel — policy allow/warn/block, a verification result, a
 * finished run. The tone is the message, so it is never decorative.
 */
export function StatusBlock({
  tone = "neutral",
  icon: Icon,
  title,
  trailing,
  children,
  className,
}: {
  tone?: Tone;
  icon?: LucideIcon;
  title?: ReactNode;
  trailing?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn("rounded-2xl border p-5", surfaces[tone], className)}
      role={tone === "block" ? "alert" : undefined}
    >
      {title || trailing ? (
        <div className="mb-2 flex items-start justify-between gap-3">
          <div className={cn("flex items-center gap-2", inks[tone])}>
            {Icon ? <Icon aria-hidden className="size-4 shrink-0" /> : null}
            <span className="text-sm font-semibold">{title}</span>
          </div>
          {trailing}
        </div>
      ) : null}
      {children ? (
        <div className="text-sm leading-relaxed text-muted">{children}</div>
      ) : null}
    </div>
  );
}
