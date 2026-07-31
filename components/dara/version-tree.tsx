import { Badge, cn, type Tone } from "../ui";

export type VersionNode = {
  id: string;
  parentId: string | null;
  status: "running" | "rejected" | "approved" | "failed";
  label: string;
  prompt: string | null;
  provider: string | null;
  model: string | null;
  qaScore: number | null;
};

const tone: Record<VersionNode["status"], Tone> = {
  running: "warn",
  rejected: "block",
  approved: "allow",
  failed: "block",
};

/**
 * A compact run-lineage tree. Parent links stay visible even when an attempt
 * fails, because hiding rejected work would make the provenance incomplete.
 */
export function VersionTree({ nodes }: { nodes: VersionNode[] }) {
  if (nodes.length === 0) return null;

  return (
    <ol aria-label="Version tree" className="grid gap-0">
      {nodes.map((node, index) => (
        <li
          className={cn(
            "relative grid grid-cols-[24px_minmax(0,1fr)] gap-3",
            index > 0 && "pl-5",
          )}
          key={node.id}
        >
          <span aria-hidden className="relative flex justify-center">
            {index < nodes.length - 1 ? (
              <span className="absolute bottom-0 top-5 w-px bg-line" />
            ) : null}
            {index > 0 ? (
              <span className="absolute -left-5 top-0 h-5 w-8 rounded-bl-xl border-b border-l border-line" />
            ) : null}
            <span className="relative mt-4 size-2.5 rounded-full border-2 border-surface bg-accent" />
          </span>
          <div className="mb-3 rounded-xl border border-line bg-inset px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                  {node.label}
                </p>
                <p className="mt-1 font-mono text-[11px] text-faint">{node.id}</p>
              </div>
              <Badge dot tone={tone[node.status]}>
                {node.status}
              </Badge>
            </div>
            {node.prompt ? (
              <p className="mt-3 text-xs leading-relaxed text-muted">{node.prompt}</p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-subtle">
              <span>
                {node.provider ?? "dara"} / {node.model ?? "control-plane"}
              </span>
              <span>
                QA {node.qaScore == null ? "—" : node.qaScore.toFixed(2)} / 1.00
              </span>
              {node.parentId ? <span>parent {node.parentId}</span> : null}
            </div>
          </div>
        </li>
      ))}
    </ol>
  );
}
