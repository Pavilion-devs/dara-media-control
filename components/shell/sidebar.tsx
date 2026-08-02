"use client";

import { Menu, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Brand } from "./brand";
import { appNav, isActive } from "./nav-items";
import { cn } from "../ui/cn";
import { ThemeToggle } from "../ui/theme-toggle";

function NavList({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <nav aria-label="Primary" className="grid gap-1">
      {appNav.map((item) => {
        const active = isActive(pathname, item);
        return (
          <Link
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors",
              active
                ? "bg-inset font-semibold text-ink"
                : "font-medium text-muted hover:bg-inset hover:text-ink",
            )}
            href={item.href}
            key={item.href}
            onClick={onNavigate}
          >
            <item.icon
              aria-hidden
              className={cn("size-4 shrink-0", active && "text-accent")}
              strokeWidth={active ? 2.25 : 2}
            />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}

function WorkspaceFooter() {
  return (
    <div className="grid gap-3 border-t border-line px-3 pt-4">
      <div className="flex items-center gap-2 text-xs text-subtle">
        <span
          aria-hidden
          className="size-1.5 shrink-0 animate-pulse rounded-full bg-verified"
        />
        Production workspace · B2 connected
      </div>
      <ThemeToggle />
    </div>
  );
}

export function Sidebar() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {/* Mobile bar */}
      <div className="sticky top-0 z-40 flex items-center justify-between gap-3 border-b border-line bg-page/85 px-4 py-3 backdrop-blur-md lg:hidden">
        <Brand />
        <button
          aria-expanded={open}
          aria-label={open ? "Close navigation" : "Open navigation"}
          className="rounded-xl border border-line p-2 text-muted transition-colors hover:bg-inset hover:text-ink"
          onClick={() => setOpen((value) => !value)}
          type="button"
        >
          {open ? (
            <X aria-hidden className="size-4" />
          ) : (
            <Menu aria-hidden className="size-4" />
          )}
        </button>
      </div>

      {open ? (
        <div className="border-b border-line bg-surface px-4 py-4 lg:hidden">
          <NavList onNavigate={() => setOpen(false)} />
          <div className="mt-4">
            <WorkspaceFooter />
          </div>
        </div>
      ) : null}

      {/* Desktop rail */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col justify-between border-r border-line bg-surface px-4 py-6 lg:flex">
        <div className="grid gap-8">
          <Brand className="px-3" />
          <NavList />
        </div>
        <WorkspaceFooter />
      </aside>
    </>
  );
}
