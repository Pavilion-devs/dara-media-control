"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "dara-theme";

const options: Array<{ value: Theme; label: string; Icon: typeof Sun }> = [
  { value: "light", label: "Light", Icon: Sun },
  { value: "system", label: "System", Icon: Monitor },
  { value: "dark", label: "Dark", Icon: Moon },
];

// The stored preference is external state, so it is read through a store rather
// than copied into an effect. Cross-tab writes land via the storage event.
const listeners = new Set<() => void>();

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

function readTheme(): Theme {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    // Private browsing can reject storage reads; fall through to the default.
  }
  return "system";
}

function serverTheme(): Theme {
  return "system";
}

function writeTheme(next: Theme) {
  if (next === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = next;

  try {
    if (next === "system") localStorage.removeItem(STORAGE_KEY);
    else localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // The switch still applies; it just will not survive a reload.
  }
  listeners.forEach((notify) => notify());
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, readTheme, serverTheme);

  return (
    <div
      aria-label="Colour theme"
      className="inline-flex items-center gap-0.5 rounded-full border border-line bg-inset p-0.5"
      role="radiogroup"
    >
      {options.map(({ value, label, Icon }) => (
        <button
          aria-checked={theme === value}
          className={`flex size-7 items-center justify-center rounded-full transition-colors ${
            theme === value
              ? "bg-surface text-ink shadow-sm"
              : "text-faint hover:text-muted"
          }`}
          key={value}
          onClick={() => writeTheme(value)}
          role="radio"
          title={label}
          type="button"
        >
          <Icon aria-hidden className="size-3.5" strokeWidth={2} />
          <span className="sr-only">{label}</span>
        </button>
      ))}
    </div>
  );
}
