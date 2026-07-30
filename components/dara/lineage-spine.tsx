import { cn } from "../ui/cn";

export type LineageNode = {
  key: string;
  step: string;
  title: string;
  detail: string;
  trailing?: string;
};

/**
 * A single vertical rule with a node per generation. Parent runs continue up the
 * spine — this is why provenance reads vertically rather than as a card grid.
 */
export function LineageSpine({
  nodes,
  className,
}: {
  nodes: LineageNode[];
  className?: string;
}) {
  return (
    <ol className={cn("relative grid gap-6", className)}>
      {nodes.map((node, index) => (
        <li className="relative grid gap-1 pl-8" key={node.key}>
          {/* Connector stops at the last node so the rule never dangles. */}
          {index < nodes.length - 1 ? (
            <span
              aria-hidden
              className="absolute left-[5px] top-4 -bottom-6 w-px bg-line"
            />
          ) : null}
          <span
            aria-hidden
            className="absolute left-0 top-1.5 size-[11px] rounded-full border-2 border-verified bg-surface"
          />
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <span className="font-mono text-[11px] uppercase tracking-wider text-subtle">
              {node.step}
            </span>
            {node.trailing ? (
              <span className="font-mono text-xs text-subtle">
                {node.trailing}
              </span>
            ) : null}
          </div>
          <p className="text-sm font-semibold text-ink">{node.title}</p>
          <p className="break-all font-mono text-xs text-muted">{node.detail}</p>
        </li>
      ))}
    </ol>
  );
}
