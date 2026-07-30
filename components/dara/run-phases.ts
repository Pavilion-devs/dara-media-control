import type { StepState } from "../ui";

/**
 * Every event the corpus emits maps to one of five pipeline phases. The flat
 * event log is really a five-stage progression, so Studio renders it as one.
 */
export const PHASES = [
  { key: "policy", label: "Policy", types: ["policy.allowed", "policy.blocked"] },
  { key: "expand", label: "Expand", types: ["prompt.expansion.completed"] },
  {
    key: "generate",
    label: "Generate",
    types: ["step.started", "step.completed", "step.failover"],
  },
  {
    key: "qa",
    label: "Vision QA",
    types: ["agent.iteration.evaluated", "qa.revised"],
  },
  {
    key: "publish",
    label: "Publish",
    types: ["publish.completed", "run.completed", "run.failed"],
  },
] as const;

export type PhaseKey = (typeof PHASES)[number]["key"];

export function phaseOf(eventType: string): PhaseKey | null {
  const match = PHASES.find((phase) =>
    (phase.types as readonly string[]).includes(eventType),
  );
  return match?.key ?? null;
}

/**
 * Derive per-phase state from the events seen so far. A policy block stops the
 * run at phase one — nothing downstream ever ran, and the timeline says so
 * rather than implying skipped work.
 */
export function derivePhases(
  eventTypes: string[],
  running: boolean,
): Array<{ key: string; label: string; state: StepState }> {
  const blocked = eventTypes.includes("policy.blocked");
  const failed = eventTypes.includes("run.failed");

  const reached = PHASES.map((phase) =>
    eventTypes.some((type) => (phase.types as readonly string[]).includes(type)),
  );
  const lastReached = reached.reduce(
    (last, seen, index) => (seen ? index : last),
    -1,
  );

  return PHASES.map((phase, index) => {
    let state: StepState;
    if (blocked) {
      state = index === 0 ? "failed" : "upcoming";
    } else if (index < lastReached) {
      state = "done";
    } else if (index === lastReached) {
      state = failed ? "failed" : running ? "current" : "done";
    } else {
      state = "upcoming";
    }
    return { key: phase.key, label: phase.label, state };
  });
}
