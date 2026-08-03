import {
  Info,
  Lightbulb,
  ShieldAlert,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "../ui/cn";

type CalloutType = "note" | "tip" | "warning" | "danger";

const VARIANTS: Record<
  CalloutType,
  { Icon: LucideIcon; ring: string; tint: string; mark: string }
> = {
  note: {
    Icon: Info,
    ring: "border-accent/30",
    tint: "bg-accent/[0.06]",
    mark: "text-accent",
  },
  tip: {
    Icon: Lightbulb,
    ring: "border-verified/30",
    tint: "bg-verified/[0.06]",
    mark: "text-verified",
  },
  warning: {
    Icon: TriangleAlert,
    ring: "border-pending/30",
    tint: "bg-pending/[0.06]",
    mark: "text-pending",
  },
  danger: {
    Icon: ShieldAlert,
    ring: "border-blocked/30",
    tint: "bg-blocked/[0.06]",
    mark: "text-blocked",
  },
};

export function Callout({
  type = "note",
  title,
  children,
}: {
  type?: CalloutType;
  title?: string;
  children: ReactNode;
}) {
  const variant = VARIANTS[type];
  return (
    <div
      className={cn(
        "my-5 flex gap-3 rounded-xl border px-4 py-3.5",
        variant.ring,
        variant.tint,
      )}
      role={type === "danger" ? "alert" : undefined}
    >
      <variant.Icon
        aria-hidden
        className={cn("mt-0.5 size-5 shrink-0", variant.mark)}
      />
      <div className="min-w-0 text-[14px] leading-relaxed text-muted [&>p]:m-0 [&>p+p]:mt-2">
        {title ? <p className="mb-1 font-semibold text-ink">{title}</p> : null}
        {children}
      </div>
    </div>
  );
}

export default Callout;
