"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { Brand } from "./brand";
import { publicNav, isActive } from "./nav-items";
import { buttonClass } from "../ui/button";
import { cn } from "../ui/cn";
import { ThemeToggle } from "../ui/theme-toggle";

/**
 * Chrome for the public trust surfaces. Deliberately light: these pages are
 * seen by clients and auditors, so they should read as a record, not a
 * dashboard.
 */
export function Navbar() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-50 border-b border-line bg-page/85 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[1800px] items-center justify-between gap-6 px-6 py-4 md:px-12 md:py-5">
        <Brand />
        <div className="flex items-center gap-2 md:gap-6">
          <nav aria-label="Primary" className="flex items-center gap-1">
            {publicNav.map((item) => (
              <Link
                aria-current={isActive(pathname, item) ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive(pathname, item)
                    ? "text-ink"
                    : "text-muted hover:text-ink",
                )}
                href={item.href}
                key={item.href}
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <ThemeToggle />
          <Link
            className={buttonClass({ size: "sm", pill: true })}
            href="/studio"
          >
            Open Studio
          </Link>
        </div>
      </div>
    </header>
  );
}
