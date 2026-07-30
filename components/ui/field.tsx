import type {
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

import { cn } from "./cn";

const control =
  "w-full rounded-xl border border-line bg-inset px-4 py-3 text-sm text-ink " +
  "placeholder:text-faint transition-colors " +
  "focus:border-accent/40 focus:outline-none focus:ring-2 focus:ring-accent/20 " +
  "disabled:cursor-not-allowed disabled:opacity-50";

export function Label({
  children,
  htmlFor,
}: {
  children: ReactNode;
  htmlFor?: string;
}) {
  return (
    <label
      className="text-xs font-semibold uppercase tracking-wider text-subtle"
      htmlFor={htmlFor}
    >
      {children}
    </label>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  children,
  className,
}: {
  label: ReactNode;
  htmlFor?: string;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid gap-2", className)}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint ? (
        <p className="text-xs leading-relaxed text-subtle">{hint}</p>
      ) : null}
    </div>
  );
}

/** `mono` marks a value the system recorded, per Dara's mono/sans split. */
export function Input({
  className,
  mono = false,
  ...props
}: { mono?: boolean } & InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input className={cn(control, mono && "font-mono", className)} {...props} />
  );
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(control, "min-h-28 resize-y leading-relaxed", className)}
      {...props}
    />
  );
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(control, "appearance-none", className)} {...props}>
      {children}
    </select>
  );
}

/** Segmented control — the template's pill row, used for mode/ratio choices. */
export function Segmented<T extends string>({
  ariaLabel,
  onChange,
  options,
  value,
}: {
  ariaLabel: string;
  onChange: (next: T) => void;
  options: Array<{ value: T; label: string }>;
  value: T;
}) {
  return (
    <div
      aria-label={ariaLabel}
      className="grid gap-1 rounded-xl border border-line bg-inset p-1"
      role="group"
      style={{ gridTemplateColumns: `repeat(${options.length}, 1fr)` }}
    >
      {options.map((option) => (
        <button
          aria-pressed={value === option.value}
          className={cn(
            "rounded-lg px-3 py-2 text-xs font-semibold transition-colors",
            value === option.value
              ? "bg-surface text-ink shadow-sm"
              : "text-subtle hover:text-ink",
          )}
          key={option.value}
          onClick={() => onChange(option.value)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
