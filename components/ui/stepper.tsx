import { Check, Loader2, X } from "lucide-react";

import { cn } from "./cn";

export type StepState = "done" | "current" | "upcoming" | "failed";

export type Step = {
  key: string;
  label: string;
  state: StepState;
};

const circles: Record<StepState, string> = {
  done: "bg-accent text-accent-contrast",
  current: "bg-accent text-accent-contrast",
  upcoming: "bg-inset text-faint",
  failed: "bg-blocked text-white",
};

/**
 * Horizontal progress across a known sequence — Dara's four policy enforcement
 * points, or the steps of a pipeline run.
 */
export function Stepper({ steps }: { steps: Step[] }) {
  return (
    <div>
      <ol className="flex items-center">
        {steps.map((step, index) => (
          <li
            className={cn("flex items-center", index > 0 && "flex-1")}
            key={step.key}
          >
            {index > 0 ? (
              <span
                aria-hidden
                className={cn(
                  "mx-1 h-0.5 flex-1",
                  steps[index - 1].state === "done" ? "bg-accent" : "bg-line",
                )}
              />
            ) : null}
            <span
              className={cn(
                "flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold",
                circles[step.state],
              )}
            >
              {step.state === "done" ? (
                <Check aria-hidden className="size-4" />
              ) : step.state === "failed" ? (
                <X aria-hidden className="size-4" />
              ) : step.state === "current" ? (
                <Loader2 aria-hidden className="size-4 animate-spin" />
              ) : (
                index + 1
              )}
              <span className="sr-only">{step.state}</span>
            </span>
          </li>
        ))}
      </ol>
      <div className="mt-2 flex items-start justify-between gap-2">
        {steps.map((step) => (
          <span
            className="max-w-20 text-[10px] leading-tight text-subtle"
            key={step.key}
          >
            {step.label}
          </span>
        ))}
      </div>
    </div>
  );
}
