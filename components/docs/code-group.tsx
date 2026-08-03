"use client";

import {
  Children,
  cloneElement,
  isValidElement,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { cn } from "../ui/cn";

type BlockProps = {
  title?: string;
  children?: ReactElement<{ className?: string; title?: string }>;
  inGroup?: boolean;
};

/**
 * Tabbed set of code blocks. Each child is one fenced block; its tab label comes
 * from the fence's `title` (```bash title="Shell"), falling back to the
 * language, then to a positional label.
 */
export function CodeGroup({ children }: { children: ReactNode }) {
  const blocks = Children.toArray(children).filter(
    isValidElement,
  ) as Array<ReactElement<BlockProps>>;
  const [active, setActive] = useState(0);

  if (blocks.length === 0) return null;

  function labelFor(block: ReactElement<BlockProps>, index: number) {
    // `title` lands on the inner <code>, because that is the element
    // mdast-util-to-hast applies fence hProperties to.
    const title = block.props?.title ?? block.props?.children?.props?.title;
    if (typeof title === "string" && title) return title;
    const className = block.props?.children?.props?.className ?? "";
    return /language-([\w-]+)/.exec(className)?.[1] ?? `Option ${index + 1}`;
  }

  return (
    <div className="my-5 overflow-hidden rounded-xl border border-line">
      <div className="flex gap-1 overflow-x-auto border-b border-line bg-inset px-2 py-1.5">
        {blocks.map((block, index) => (
          <button
            className={cn(
              "shrink-0 rounded-md px-3 py-1 text-[12.5px] font-medium transition-colors",
              index === active
                ? "bg-surface text-ink shadow-sm"
                : "text-subtle hover:text-ink",
            )}
            key={index}
            onClick={() => setActive(index)}
            type="button"
          >
            {labelFor(block, index)}
          </button>
        ))}
      </div>
      {/* Strip the child's own border and rounding so it sits flush. */}
      <div className="[&>div>div]:border-t-0 [&>div]:my-0 [&>div]:rounded-none [&>div]:border-0">
        {cloneElement(blocks[active], { inGroup: true })}
      </div>
    </div>
  );
}

export default CodeGroup;
