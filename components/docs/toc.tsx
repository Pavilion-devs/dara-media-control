"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";

import { cn } from "../ui/cn";

type Heading = { id: string; text: string; level: number };

const EMPTY: Heading[] = [];

/**
 * The rendered article is external state, so headings are read through a store
 * rather than copied into an effect. The snapshot is cached against the heading
 * ids so repeated reads return a stable reference.
 */
let cache: { key: string; items: Heading[] } = { key: "", items: EMPTY };

function readHeadings(): Heading[] {
  const article = document.getElementById("doc-article");
  if (!article) return EMPTY;

  const elements = Array.from(
    article.querySelectorAll<HTMLElement>("h2, h3"),
  ).filter((element) => element.id);

  const key = elements.map((element) => element.id).join("|");
  if (key !== cache.key) {
    cache = {
      key,
      items: elements.map((element) => ({
        id: element.id,
        text: element.innerText,
        level: element.tagName === "H3" ? 3 : 2,
      })),
    };
  }
  return cache.items;
}

function serverHeadings(): Heading[] {
  return EMPTY;
}

function subscribe(onChange: () => void) {
  // The article subtree is replaced on navigation rather than remounted.
  const observer = new MutationObserver(onChange);
  observer.observe(document.body, { childList: true, subtree: true });
  return () => observer.disconnect();
}

/** Builds the "On this page" rail from the rendered article headings. */
export function Toc() {
  const pathname = usePathname();
  const items = useSyncExternalStore(subscribe, readHeadings, serverHeadings);
  const [active, setActive] = useState("");

  useEffect(() => {
    const article = document.getElementById("doc-article");
    if (!article) return;
    const elements = Array.from(
      article.querySelectorAll<HTMLElement>("h2, h3"),
    ).filter((element) => element.id);

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) setActive(entry.target.id);
        });
      },
      { rootMargin: "-80px 0px -70% 0px" },
    );
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
  }, [pathname, items]);

  if (items.length === 0) return null;

  return (
    <aside className="sticky top-16 hidden h-[calc(100vh-4rem)] w-56 shrink-0 overflow-y-auto py-10 pr-6 xl:block">
      <p className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-faint">
        On this page
      </p>
      <ul className="space-y-1.5">
        {items.map((heading) => (
          <li className={heading.level === 3 ? "ml-3" : ""} key={heading.id}>
            <a
              className={cn(
                "block border-l-2 pl-3 text-[13px] leading-snug transition-colors",
                active === heading.id
                  ? "border-accent text-accent-ink"
                  : "border-transparent text-subtle hover:text-ink",
              )}
              href={`#${heading.id}`}
            >
              {heading.text}
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}

export default Toc;
