import { cn } from "../ui/cn";

const ITEMS = [
  {
    x: 34,
    title: "Source bytes",
    label: "MODEL OUTPUT",
    lines: ["immutable original", "source_sha256"],
    tone: "neutral",
  },
  {
    x: 224,
    title: "Manifest",
    label: "GENBLAZE PROVENANCE",
    lines: ["run · steps · params", "canonical_hash"],
    tone: "accent",
  },
  {
    x: 414,
    title: "Embed",
    label: "PRE-PUBLISH GATE",
    lines: ["prepare derivative", "extract and validate"],
    tone: "accent",
  },
  {
    x: 604,
    title: "Delivered bytes",
    label: "CLIENT ARTIFACT",
    lines: ["embedded derivative", "published_sha256"],
    tone: "verified",
  },
  {
    x: 794,
    title: "Trusted index",
    label: "BACKBLAZE B2",
    lines: ["both hashes → AssetRef", "immutable evidence"],
    tone: "verified",
  },
  {
    x: 984,
    title: "Verify",
    label: "PUBLIC VERDICT",
    lines: ["hash uploaded bytes", "resolve trusted record"],
    tone: "verified",
  },
] as const;

const TONES = {
  neutral: "var(--d-line-strong)",
  accent: "var(--d-accent)",
  verified: "var(--d-verified)",
} as const;

function Item({ item }: { item: (typeof ITEMS)[number] }) {
  const colour = TONES[item.tone];
  return (
    <g>
      <rect
        fill="var(--d-surface)"
        height="116"
        rx="12"
        stroke={colour}
        strokeWidth="1.4"
        width="166"
        x={item.x}
        y="82"
      />
      <rect fill={colour} height="4" rx="2" width="38" x={item.x + 16} y="98" />
      <text fill="var(--d-text)" fontSize="18.2" fontWeight="650" x={item.x + 16} y="128">
        {item.title}
      </text>
      <text fill="var(--d-text-3)" fontSize="13" fontWeight="650" letterSpacing="0.08em" x={item.x + 16} y="147">
        {item.label}
      </text>
      {item.lines.map((line, index) => (
        <text
          fill="var(--d-text-2)"
          fontFamily="var(--font-mono)"
          fontSize="13"
          key={line}
          x={item.x + 16}
          y={170 + index * 17}
        >
          {line}
        </text>
      ))}
    </g>
  );
}

export function ProvenanceFlowDiagram({ className }: { className?: string }) {
  return (
    <div className={cn(// Escape the prose column so the figure gets the full content width.
        "col-start-1! col-end-4! w-full rounded-2xl border border-line bg-surface p-4", className)}>
      <svg
        aria-labelledby="provenance-title provenance-description"
        className="block h-auto w-full"
        fontFamily="var(--font-sans)"
        role="img"
        viewBox="0 0 1200 326"
      >
        <title id="provenance-title">Dara provenance and verification flow</title>
        <desc id="provenance-description">
          Source bytes and a canonical manifest are preserved separately. The manifest is
          embedded into a delivered derivative with its own published hash. Both hashes
          resolve to a trusted asset record used by public verification.
        </desc>
        <defs>
          <marker
            id="provenance-arrow"
            markerHeight="7"
            markerUnits="strokeWidth"
            markerWidth="7"
            orient="auto"
            refX="6"
            refY="3.5"
          >
            <path d="M 0 0 L 7 3.5 L 0 7 z" fill="var(--d-line-strong)" />
          </marker>
          <marker
            id="provenance-arrow-record"
            markerHeight="7"
            markerUnits="strokeWidth"
            markerWidth="7"
            orient="auto"
            refX="6"
            refY="3.5"
          >
            <path d="M 0 0 L 7 3.5 L 0 7 z" fill="var(--d-verified)" />
          </marker>
        </defs>

        <text fill="var(--d-text-3)" fontSize="14.2" fontWeight="700" letterSpacing="0.12em" x="34" y="36">
          TWO HASHES · TWO BYTE ROLES · ONE TRUSTED RECORD
        </text>
        <text fill="var(--d-text-2)" fontSize="16.2" x="34" y="59">
          Embedding changes the file, so Dara never compares the delivered bytes to the source hash.
        </text>

        {ITEMS.slice(0, -1).map((item, index) => {
          const next = ITEMS[index + 1];
          const recordPath = index >= 3;
          return (
            <line
              key={`${item.title}-${next.title}`}
              markerEnd={recordPath ? "url(#provenance-arrow-record)" : "url(#provenance-arrow)"}
              stroke={recordPath ? "var(--d-verified)" : "var(--d-line-strong)"}
              strokeWidth="1.5"
              x1={item.x + 166}
              x2={next.x - 8}
              y1="140"
              y2="140"
            />
          );
        })}
        {ITEMS.map((item) => (
          <Item item={item} key={item.title} />
        ))}

        <path
          d="M 116 198 C 116 244 795 248 862 198"
          fill="none"
          markerEnd="url(#provenance-arrow-record)"
          stroke="var(--d-verified)"
          strokeDasharray="5 5"
          strokeWidth="1.4"
        />
        <rect fill="var(--d-surface)" height="21" rx="6" width="228" x="374" y="231" />
        <text fill="var(--d-verified-ink)" fontSize="13.5" fontWeight="650" textAnchor="middle" x="488" y="246">
          source hash also resolves through the index
        </text>

        <g>
          {[
            ["trusted-match", "manifest valid + delivered hash matches B2", "var(--d-verified)"],
            ["trusted-mismatch", "trusted record found, bytes differ", "var(--d-blocked)"],
            ["self-consistent", "manifest valid, no trusted Dara record", "var(--d-pending)"],
          ].map(([label, detail, colour], index) => {
            const x = 34 + index * 358;
            return (
              <g key={label}>
                <circle cx={x + 5} cy="296" fill={colour} r="4" />
                <text fill="var(--d-text)" fontSize="14.2" fontWeight="650" x={x + 16} y="300">
                  {label}
                </text>
                <text fill="var(--d-text-3)" fontSize="13" x={x + 112} y="300">
                  {detail}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

export default ProvenanceFlowDiagram;
