import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "./cn";

type Variant = "primary" | "secondary" | "accent" | "ghost";
type Size = "sm" | "md" | "lg";

/**
 * `primary` inverts against the page, so it reads as near-black on light and
 * near-white on dark without a per-theme override.
 */
const variants: Record<Variant, string> = {
  primary: "bg-ink text-page hover:opacity-90",
  secondary: "border border-line bg-surface text-ink hover:bg-inset",
  accent: "bg-accent text-accent-contrast hover:opacity-90",
  ghost: "text-muted hover:bg-inset hover:text-ink",
};

const sizes: Record<Size, string> = {
  sm: "h-9 px-3 text-xs",
  md: "h-11 px-4 text-sm",
  lg: "h-12 px-6 text-sm",
};

export function buttonClass({
  variant = "primary",
  size = "md",
  pill = false,
  full = false,
  className,
}: {
  variant?: Variant;
  size?: Size;
  pill?: boolean;
  full?: boolean;
  className?: string;
} = {}) {
  return cn(
    "inline-flex items-center justify-center gap-2 font-semibold transition-colors",
    "disabled:cursor-not-allowed disabled:opacity-40",
    pill ? "rounded-full" : "rounded-xl",
    full && "w-full",
    variants[variant],
    sizes[size],
    className,
  );
}

export function Button({
  variant,
  size,
  pill,
  full,
  className,
  children,
  ...props
}: {
  variant?: Variant;
  size?: Size;
  pill?: boolean;
  full?: boolean;
  children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={buttonClass({ variant, size, pill, full, className })}
      {...props}
    >
      {children}
    </button>
  );
}
