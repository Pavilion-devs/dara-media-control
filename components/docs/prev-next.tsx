"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { flatDocs } from "@/lib/docs-nav";

export function PrevNext() {
  const pathname = usePathname();
  const index = flatDocs.findIndex((doc) => doc.slug === pathname);
  if (index === -1) return null;

  const previous = index > 0 ? flatDocs[index - 1] : null;
  const next = index < flatDocs.length - 1 ? flatDocs[index + 1] : null;

  return (
    <nav
      aria-label="Pagination"
      className="mt-16 grid grid-cols-2 gap-4 border-t border-line pt-8"
    >
      <div>
        {previous ? (
          <Link
            className="flex flex-col rounded-xl border border-line p-4 transition-colors hover:border-line-strong"
            href={previous.slug}
          >
            <span className="flex items-center gap-1 text-[12px] text-faint">
              <ArrowLeft aria-hidden className="size-3.5" /> Previous
            </span>
            <span className="mt-1 text-[14px] font-medium text-ink">
              {previous.title}
            </span>
          </Link>
        ) : null}
      </div>
      <div>
        {next ? (
          <Link
            className="flex flex-col items-end rounded-xl border border-line p-4 text-right transition-colors hover:border-line-strong"
            href={next.slug}
          >
            <span className="flex items-center gap-1 text-[12px] text-faint">
              Next <ArrowRight aria-hidden className="size-3.5" />
            </span>
            <span className="mt-1 text-[14px] font-medium text-ink">
              {next.title}
            </span>
          </Link>
        ) : null}
      </div>
    </nav>
  );
}

export default PrevNext;
