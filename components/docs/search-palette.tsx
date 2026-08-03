"use client";

import { Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

import { flatDocs } from "@/lib/docs-nav";
import { cn } from "../ui/cn";

export const OPEN_SEARCH_EVENT = "dara:open-search";

export function SearchPalette() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);

  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return flatDocs;
    return flatDocs.filter(
      (doc) =>
        doc.title.toLowerCase().includes(needle)
        || doc.summary.toLowerCase().includes(needle),
    );
  }, [query]);

  useEffect(() => {
    function onOpen() {
      setOpen(true);
      setQuery("");
      setCursor(0);
    }
    function onKey(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        onOpen();
      }
      if (event.key === "Escape") setOpen(false);
    }
    window.addEventListener(OPEN_SEARCH_EVENT, onOpen);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener(OPEN_SEARCH_EVENT, onOpen);
      window.removeEventListener("keydown", onKey);
    };
  }, []);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  if (!open) return null;

  function go(slug: string) {
    setOpen(false);
    router.push(slug);
  }

  return (
    <div
      aria-modal
      className="fixed inset-0 z-[100] flex items-start justify-center bg-ink/40 px-4 pt-[12vh] backdrop-blur-sm"
      onClick={() => setOpen(false)}
      role="dialog"
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-line px-4">
          <Search aria-hidden className="size-4 shrink-0 text-faint" />
          <input
            aria-label="Search documentation"
            className="w-full bg-transparent py-3.5 text-sm text-ink outline-none placeholder:text-faint"
            onChange={(event) => {
              setQuery(event.target.value);
              setCursor(0);
            }}
            onKeyDown={(event) => {
              if (event.key === "ArrowDown") {
                event.preventDefault();
                setCursor((c) => Math.min(c + 1, results.length - 1));
              }
              if (event.key === "ArrowUp") {
                event.preventDefault();
                setCursor((c) => Math.max(c - 1, 0));
              }
              if (event.key === "Enter" && results[cursor]) {
                go(results[cursor].slug);
              }
            }}
            placeholder="Search the documentation…"
            ref={inputRef}
            value={query}
          />
          <kbd className="hidden shrink-0 rounded border border-line px-1.5 text-[10px] text-faint sm:block">
            ESC
          </kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-2">
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-sm text-subtle">
              Nothing matches that. Try a different term.
            </li>
          ) : (
            results.map((doc, index) => (
              <li key={doc.slug}>
                <button
                  className={cn(
                    "w-full rounded-lg px-3 py-2 text-left transition-colors",
                    index === cursor ? "bg-inset" : "hover:bg-inset",
                  )}
                  onClick={() => go(doc.slug)}
                  onMouseEnter={() => setCursor(index)}
                  type="button"
                >
                  <span className="block text-sm font-medium text-ink">
                    {doc.title}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-subtle">
                    {doc.summary}
                  </span>
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}

export default SearchPalette;
