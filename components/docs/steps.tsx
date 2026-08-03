import { Children, isValidElement, type ReactNode } from "react";

/**
 * Numbered walkthrough. The connecting rule is drawn by the container rather
 * than by each step, so the last step does not trail a dangling line.
 */
export function Steps({ children }: { children: ReactNode }) {
  const steps = Children.toArray(children).filter(isValidElement);
  return (
    <div className="my-6">
      {steps.map((step, index) => (
        <div className="relative flex gap-4 pb-8 last:pb-0" key={index}>
          {index < steps.length - 1 ? (
            <span
              aria-hidden
              className="absolute bottom-0 left-[15px] top-9 w-px bg-line"
            />
          ) : null}
          <span className="relative z-10 grid size-8 shrink-0 place-items-center rounded-full border border-line bg-surface text-[13px] font-semibold text-ink">
            {index + 1}
          </span>
          <div className="min-w-0 flex-1 pt-0.5">{step}</div>
        </div>
      ))}
    </div>
  );
}

export function Step({
  title,
  children,
}: {
  title: string;
  children?: ReactNode;
}) {
  return (
    <>
      <p className="m-0 text-[15px] font-semibold tracking-tight text-ink">
        {title}
      </p>
      <div className="[&>*:first-child]:mt-2 [&>*:last-child]:mb-0">
        {children}
      </div>
    </>
  );
}

export default Steps;
