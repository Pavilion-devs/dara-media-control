"use client";

import { Check, Copy } from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
} from "react";

type CodeChildProps = { className?: string; title?: string };

/**
 * Wraps fenced code blocks (mapped from MDX `pre`) with a language label and a
 * copy button. No syntax tokenizing, so it stays dependency-free.
 */
export function CodeBlock({
  children,
  inGroup = false,
  ...props
}: {
  children?: ReactNode;
  /** Set by <CodeGroup>, whose tab already shows the title. */
  inGroup?: boolean;
} & HTMLAttributes<HTMLPreElement>) {
  const ref = useRef<HTMLPreElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current);
    },
    [],
  );

  const codeChild = children as ReactElement<CodeChildProps> | undefined;
  const childClass = codeChild?.props?.className ?? "";
  const language = /language-([\w-]+)/.exec(childClass)?.[1] ?? "code";
  // A fence `title="…"` wins over the bare language — except inside a
  // CodeGroup, where the tab already shows it.
  const title = inGroup ? undefined : codeChild?.props?.title;

  async function copy() {
    try {
      await navigator.clipboard.writeText(ref.current?.innerText ?? "");
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied; the text stays selectable by hand.
    }
  }

  return (
    <div className="group relative my-5 overflow-hidden rounded-xl border border-line bg-inset">
      <div className="flex items-center justify-between border-b border-line px-4 py-2">
        <span
          className={
            title
              ? "text-[12px] font-medium text-subtle"
              : "font-mono text-[11px] uppercase tracking-wider text-faint"
          }
        >
          {title ?? language}
        </span>
        <button
          aria-label="Copy code"
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[12px] text-subtle transition-colors hover:text-ink"
          onClick={() => void copy()}
          type="button"
        >
          {copied ? (
            <Check aria-hidden className="size-3.5 text-verified" />
          ) : (
            <Copy aria-hidden className="size-3.5" />
          )}
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <pre
        {...props}
        className="overflow-x-auto p-4 font-mono text-[13px] leading-relaxed text-ink"
        ref={ref}
      >
        {children}
      </pre>
    </div>
  );
}

export default CodeBlock;
