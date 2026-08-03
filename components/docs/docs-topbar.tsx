"use client";

import { Search } from "lucide-react";
import Link from "next/link";

import { Brand } from "../shell/brand";
import { buttonClass } from "../ui/button";
import { ThemeToggle } from "../ui/theme-toggle";
import { OPEN_SEARCH_EVENT, SearchPalette } from "./search-palette";

const openSearch = () => window.dispatchEvent(new Event(OPEN_SEARCH_EVENT));

export function DocsTopbar() {
  return (
    <header className="sticky top-0 z-50 border-b border-line bg-page/85 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-[1600px] items-center gap-3 px-4 lg:px-6">
        <Link className="flex items-center gap-2.5" href="/docs">
          <Brand href="/docs" />
          <span className="text-[15px] font-medium tracking-tight text-faint">
            Docs
          </span>
        </Link>

        <div className="flex-1" />

        <button
          className="hidden items-center gap-2 rounded-lg border border-line bg-inset px-3 py-1.5 text-[13px] text-faint transition-colors hover:border-line-strong sm:flex"
          onClick={openSearch}
          type="button"
        >
          <Search aria-hidden className="size-4" />
          Search
          <kbd className="ml-6 rounded border border-line px-1.5 text-[10px]">
            ⌘K
          </kbd>
        </button>
        <button
          aria-label="Search"
          className="grid size-9 place-items-center rounded-lg text-subtle hover:bg-inset sm:hidden"
          onClick={openSearch}
          type="button"
        >
          <Search aria-hidden className="size-[18px]" />
        </button>

        <Link
          className="hidden text-[14px] font-medium text-muted transition-colors hover:text-ink md:block"
          href="/docs/architecture"
        >
          Architecture
        </Link>

        <ThemeToggle />

        <Link
          className={buttonClass({ pill: true, size: "sm" })}
          href="/studio"
        >
          Open Studio
        </Link>
      </div>
      <SearchPalette />
    </header>
  );
}

export default DocsTopbar;
