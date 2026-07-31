import type { ReactNode } from "react";

import { cn } from "./cn";

/**
 * The surface every screen is built from. `overflow-hidden` is load-bearing: it
 * lets dense, square-cornered data rows sit flush inside a rounded container,
 * so tables stay legible without fighting the rounded visual language.
 */
export function Panel({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={cn(
        "min-w-0 overflow-hidden rounded-2xl border border-line bg-surface",
        className,
      )}
    >
      {children}
    </section>
  );
}

export function PanelHead({
  title,
  trailing,
  className,
}: {
  title: ReactNode;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-14 items-center justify-between gap-3 border-b border-line px-5",
        className,
      )}
    >
      {typeof title === "string" ? (
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
      ) : (
        title
      )}
      {trailing}
    </div>
  );
}

export function PanelBody({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return <div className={cn("min-w-0 p-5", className)}>{children}</div>;
}
