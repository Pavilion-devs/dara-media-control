import { icons, type LucideIcon } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { cn } from "../ui/cn";

/**
 * Icon card. Becomes a link when `href` is given and a plain panel otherwise, so
 * the same component serves "go here next" grids and static feature grids.
 *
 * `icon` takes a lucide name in PascalCase, e.g. "ShieldCheck".
 */
export function Card({
  title,
  icon,
  href,
  children,
}: {
  title: string;
  icon?: string;
  href?: string;
  children?: ReactNode;
}) {
  const Icon = icon
    ? ((icons as Record<string, LucideIcon>)[icon] ?? null)
    : null;

  const inner = (
    <>
      {Icon ? (
        <span className="mb-3 grid size-9 place-items-center rounded-lg bg-accent/10 text-accent-ink">
          <Icon aria-hidden className="size-[19px]" />
        </span>
      ) : null}
      <p className="text-[15px] font-semibold tracking-tight text-ink">
        {title}
      </p>
      {children ? (
        <div className="mt-1.5 text-[13.5px] leading-6 text-subtle [&>p]:m-0">
          {children}
        </div>
      ) : null}
    </>
  );

  const base =
    "flex flex-col rounded-xl border border-line bg-surface p-5";

  if (!href) return <div className={base}>{inner}</div>;

  const internal = href.startsWith("/") || href.startsWith("#");
  const linkClass = cn(
    base,
    "transition-colors hover:border-accent/50 hover:bg-accent/[0.03]",
  );

  return internal ? (
    <Link className={linkClass} href={href}>
      {inner}
    </Link>
  ) : (
    <a className={linkClass} href={href} rel="noreferrer" target="_blank">
      {inner}
    </a>
  );
}

/** Responsive grid wrapper. `cols` is the desktop column count. */
export function CardGroup({
  cols = 2,
  children,
}: {
  cols?: 1 | 2 | 3;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "my-6 grid grid-cols-1 gap-4",
        cols === 1
          ? "sm:grid-cols-1"
          : cols === 3
            ? "sm:grid-cols-2 lg:grid-cols-3"
            : "sm:grid-cols-2",
      )}
    >
      {children}
    </div>
  );
}

export default Card;
