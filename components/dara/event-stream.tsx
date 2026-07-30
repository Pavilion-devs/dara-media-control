"use client";

import { AlertTriangle, Check, ChevronRight, Dot, RefreshCw } from "lucide-react";
import { useState } from "react";

import { cn } from "../ui/cn";

export type RunEvent = {
  seq: number;
  time: string;
  provider: string;
  model: string;
  message: string;
  kind: string;
  tone: "normal" | "failover" | "revised" | "success";
};

function EventRow({ event }: { event: RunEvent }) {
  const failover = event.tone === "failover";
  const revised = event.tone === "revised";

  return (
    <li
      className={cn(
        "grid grid-cols-[auto_3.5rem_1fr] items-start gap-3 px-4 py-3 text-sm",
        failover && "bg-pending/10",
        revised && "bg-accent/10",
      )}
    >
      <span className="mt-0.5 flex size-4 items-center justify-center">
        {failover ? (
          <AlertTriangle aria-hidden className="size-3.5 text-pending" />
        ) : revised ? (
          <RefreshCw aria-hidden className="size-3.5 text-accent" />
        ) : event.tone === "success" ? (
          <Check aria-hidden className="size-3.5 text-verified" />
        ) : (
          <Dot aria-hidden className="size-4 text-faint" />
        )}
      </span>
      <span className="font-mono text-xs text-faint">{event.time}</span>
      <span className="min-w-0">
        <span
          className={cn(
            "block leading-relaxed",
            failover
              ? "text-pending-ink"
              : revised
                ? "text-accent-ink"
                : "text-muted",
          )}
        >
          {event.message}
        </span>
        <span className="mt-0.5 block font-mono text-[11px] text-faint">
          {event.provider} · {event.model}
        </span>
      </span>
    </li>
  );
}

/**
 * The raw log. Open by default: these events are the provenance evidence, so
 * they ship in the server-rendered record rather than hiding behind a toggle.
 * The phase timeline above carries the story; this is the proof.
 */
export function EventStream({ events }: { events: RunEvent[] }) {
  const [open, setOpen] = useState(true);

  if (events.length === 0) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <button
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-3 bg-inset px-4 py-3 text-left transition-colors hover:bg-line/40"
        onClick={() => setOpen((value) => !value)}
        type="button"
      >
        <span className="text-xs font-semibold uppercase tracking-wider text-subtle">
          Event stream
        </span>
        <span className="flex items-center gap-2 text-xs text-subtle">
          {events.length} event{events.length === 1 ? "" : "s"}
          <ChevronRight
            aria-hidden
            className={cn(
              "size-4 transition-transform",
              open && "rotate-90",
            )}
          />
        </span>
      </button>
      {open ? (
        <ul className="divide-y divide-line bg-surface">
          {events.map((event) => (
            <EventRow event={event} key={event.seq} />
          ))}
        </ul>
      ) : null}
    </div>
  );
}

/** The most recent meaningful line, shown while a run is in flight. */
export function ActiveEvent({ event }: { event: RunEvent | undefined }) {
  if (!event) return null;
  return (
    <div className="grid gap-1">
      <p className="text-base leading-relaxed text-ink">{event.message}</p>
      <p className="font-mono text-xs text-subtle">
        {event.time} · {event.provider} · {event.model}
      </p>
    </div>
  );
}
