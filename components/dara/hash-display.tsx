import { cn } from "../ui/cn";

type Tone = "verified" | "mismatch" | "neutral";

const tones: Record<Tone, string> = {
  verified: "text-verified",
  mismatch: "text-ink",
  neutral: "text-ink",
};

function blocks(value: string) {
  return value.match(/.{1,8}/g) ?? [];
}

/**
 * The signature element: a whole-file SHA-256 at display size, grouped in eight
 * blocks of eight. The grid reflows 8 → 4 → 2 columns so a 64-character hash
 * never overflows its container.
 */
export function HashDisplay({
  value,
  tone = "neutral",
  /** When set and different, characters from the first divergence are flagged. */
  diffAgainst,
  className,
}: {
  value: string;
  tone?: Tone;
  diffAgainst?: string | null;
  className?: string;
}) {
  const firstDifference =
    diffAgainst && diffAgainst !== value
      ? Array.from(value).findIndex(
          (character, index) => character !== diffAgainst[index],
        )
      : -1;

  return (
    <p
      aria-label={`SHA-256 ${value}`}
      className={cn(
        "grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-base tracking-tight sm:grid-cols-4 sm:text-lg lg:grid-cols-8 lg:text-xl",
        tones[tone],
        className,
      )}
    >
      {blocks(value).map((block, blockIndex) => (
        <span key={`${block}-${blockIndex}`}>
          {firstDifference < 0
            ? block
            : Array.from(block).map((character, characterIndex) => {
                const index = blockIndex * 8 + characterIndex;
                return (
                  <span
                    className={index >= firstDifference ? "text-blocked" : undefined}
                    key={index}
                  >
                    {character}
                  </span>
                );
              })}
        </span>
      ))}
    </p>
  );
}
