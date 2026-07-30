import Link from "next/link";

import { cn } from "../ui/cn";

/** The wordmark, split so the accent lands on the second syllable. */
export function Brand({
  className,
  href = "/",
}: {
  className?: string;
  href?: string;
}) {
  return (
    <Link
      className={cn(
        "text-xl font-semibold tracking-tight text-ink transition-opacity hover:opacity-70",
        className,
      )}
      href={href}
    >
      Da<span className="text-accent">ra</span>
    </Link>
  );
}
