import { cn } from "../ui/cn";

/**
 * Dara's deployment and trust boundaries.
 *
 * Sized for the space it actually gets. The canvas is 1000 units wide against a
 * ~1024px full-bleed column, so it renders near 1:1 and nothing drops below 12
 * units — the previous version put most of its labels at 7px inside a 768px
 * prose column, which forced a sideways scroll on every screen.
 *
 * Per-component detail lives in the table beneath the figure rather than being
 * drawn: a sentence rendered as SVG text cannot be read, searched or selected.
 *
 * Colours are CSS custom properties so they resolve inside <marker> defs too,
 * which is what lets the diagram follow the theme toggle.
 */

type Tone = "request" | "provider" | "record";

const COLOURS: Record<Tone, string> = {
  request: "var(--d-accent)",
  provider: "var(--d-pending)",
  record: "var(--d-verified)",
};

const LANES = [
  { x: 16, w: 218, label: "Browser" },
  { x: 250, w: 210, label: "Web boundary" },
  { x: 476, w: 254, label: "Control plane" },
  { x: 746, w: 238, label: "External systems" },
] as const;

type Card = {
  x: number;
  y: number;
  w: number;
  h: number;
  title: string;
  eyebrow?: string;
  rows?: string[];
  tone?: "plain" | "accent" | "verified";
};

const CARDS: Card[] = [
  {
    x: 32,
    y: 92,
    w: 186,
    h: 96,
    title: "Public surfaces",
    eyebrow: "No account",
    rows: ["/verify · /share"],
  },
  {
    x: 32,
    y: 208,
    w: 186,
    h: 96,
    title: "Workspace UI",
    eyebrow: "Operator",
    rows: ["/studio · /runs · /ledger"],
  },
  {
    x: 32,
    y: 324,
    w: 186,
    h: 96,
    title: "Browser runtime",
    eyebrow: "Client-side",
    rows: ["Hashes files locally"],
  },
  {
    x: 264,
    y: 92,
    w: 182,
    h: 92,
    title: "HAProxy",
    eyebrow: "TLS · public ingress",
    rows: ["usedara.xyz"],
  },
  {
    x: 264,
    y: 204,
    w: 182,
    h: 216,
    title: "Next.js",
    eyebrow: "Backend-for-frontend",
    rows: ["Route handlers", "Holds the token", "Anonymous actor", "SSE proxy"],
    tone: "accent",
  },
  {
    x: 490,
    y: 92,
    w: 226,
    h: 328,
    title: "FastAPI",
    eyebrow: "Single instance",
    rows: [
      "API boundary",
      "Policy & admission",
      "Genblaze job runtime",
      "Publish & verify",
      "DuckDB ledger reader",
    ],
  },
  {
    x: 760,
    y: 92,
    w: 210,
    h: 84,
    title: "OpenAI",
    eyebrow: "Primary provider",
    rows: ["image · video · speech"],
  },
  {
    x: 760,
    y: 196,
    w: 210,
    h: 76,
    title: "Replicate",
    eyebrow: "Diverse fallback",
    rows: ["FLUX 1.1 Pro"],
  },
  {
    x: 760,
    y: 292,
    w: 210,
    h: 128,
    title: "Backblaze B2",
    eyebrow: "Only datastore",
    rows: ["Control state", "Evidence", "Accounting Parquet"],
    tone: "verified",
  },
];

type Edge = {
  d: string;
  tone: Tone;
  label: string;
  x: number;
  y: number;
  dashed?: boolean;
};

const EDGES: Edge[] = [
  { d: "M 218 138 L 262 138", tone: "request", label: "HTTPS", x: 240, y: 126 },
  {
    d: "M 355 184 L 355 202",
    tone: "request",
    label: "private",
    x: 355,
    y: 199,
  },
  {
    d: "M 446 312 L 488 312",
    tone: "request",
    label: "loopback · SSE",
    x: 467,
    y: 300,
  },
  {
    d: "M 716 134 L 758 134",
    tone: "provider",
    label: "paid call",
    x: 737,
    y: 122,
    dashed: true,
  },
  {
    d: "M 716 234 L 758 234",
    tone: "provider",
    label: "fallback",
    x: 737,
    y: 222,
    dashed: true,
  },
  {
    d: "M 716 356 L 758 356",
    tone: "record",
    label: "S3 read / write",
    x: 737,
    y: 344,
  },
];

function Marker({ id, colour }: { id: string; colour: string }) {
  return (
    <marker
      id={id}
      markerHeight="7"
      markerUnits="strokeWidth"
      markerWidth="7"
      orient="auto"
      refX="6"
      refY="3.5"
    >
      <path d="M 0 0 L 7 3.5 L 0 7 z" fill={colour} />
    </marker>
  );
}

function CardShape({ card }: { card: Card }) {
  const stroke =
    card.tone === "accent"
      ? "var(--d-accent)"
      : card.tone === "verified"
        ? "var(--d-verified)"
        : "var(--d-line-strong)";
  const fill =
    card.tone === "accent"
      ? "color-mix(in srgb, var(--d-accent) 7%, var(--d-surface))"
      : card.tone === "verified"
        ? "color-mix(in srgb, var(--d-verified) 7%, var(--d-surface))"
        : "var(--d-surface)";

  return (
    <g>
      <rect
        fill={fill}
        height={card.h}
        rx="12"
        stroke={stroke}
        strokeWidth="1.5"
        width={card.w}
        x={card.x}
        y={card.y}
      />
      <text
        fill="var(--d-text)"
        fontSize="17"
        fontWeight="650"
        x={card.x + 16}
        y={card.y + 30}
      >
        {card.title}
      </text>
      {card.eyebrow ? (
        <text
          fill="var(--d-text-3)"
          fontSize="12"
          fontWeight="600"
          x={card.x + 16}
          y={card.y + 50}
        >
          {card.eyebrow}
        </text>
      ) : null}
      {card.rows?.map((row, index) => (
        <text
          fill="var(--d-text-2)"
          fontSize="13"
          key={row}
          x={card.x + 16}
          y={card.y + 76 + index * 26}
        >
          {row}
        </text>
      ))}
    </g>
  );
}

function EdgeShape({ edge }: { edge: Edge }) {
  const width = Math.max(52, edge.label.length * 7);
  return (
    <g>
      <path
        d={edge.d}
        fill="none"
        markerEnd={`url(#architecture-arrow-${edge.tone})`}
        stroke={COLOURS[edge.tone]}
        strokeDasharray={edge.dashed ? "5 5" : undefined}
        strokeLinecap="round"
        strokeWidth="2"
      />
      <rect
        fill="var(--d-inset)"
        height="20"
        rx="6"
        width={width}
        x={edge.x - width / 2}
        y={edge.y - 15}
      />
      <text
        fill={COLOURS[edge.tone]}
        fontSize="12"
        fontWeight="650"
        textAnchor="middle"
        x={edge.x}
        y={edge.y}
      >
        {edge.label}
      </text>
    </g>
  );
}

export function ArchitectureDiagram({
  className,
  framed = false,
}: {
  className?: string;
  framed?: boolean;
}) {
  return (
    <div
      className={cn(
        // Escape the prose column so the figure gets the full content width.
        "col-start-1! col-end-4! my-8 w-full",
        framed && "rounded-2xl border border-line bg-surface p-4",
        className,
      )}
    >
      <svg
        aria-labelledby="architecture-title architecture-description"
        className="block h-auto w-full"
        fontFamily="var(--font-sans)"
        role="img"
        viewBox="0 0 1000 500"
      >
        <title id="architecture-title">
          Dara deployment and trust boundaries
        </title>
        <desc id="architecture-description">
          Browser requests cross TLS at HAProxy, then a Next.js
          backend-for-frontend that holds the workspace token, then a single
          loopback FastAPI process owning policy, jobs, publication and
          verification. FastAPI calls OpenAI and Replicate, and reads and writes
          all durable state to one Backblaze B2 bucket.
        </desc>
        <defs>
          <Marker colour={COLOURS.request} id="architecture-arrow-request" />
          <Marker colour={COLOURS.provider} id="architecture-arrow-provider" />
          <Marker colour={COLOURS.record} id="architecture-arrow-record" />
        </defs>

        {LANES.map((lane) => (
          <g key={lane.label}>
            <rect
              fill="var(--d-inset)"
              height="392"
              rx="16"
              stroke="var(--d-line)"
              width={lane.w}
              x={lane.x}
              y="44"
            />
            <text
              fill="var(--d-text-3)"
              fontSize="12"
              fontWeight="700"
              letterSpacing="0.1em"
              x={lane.x + 16}
              y="72"
            >
              {lane.label.toUpperCase()}
            </text>
          </g>
        ))}

        {CARDS.map((card) => (
          <CardShape card={card} key={card.title} />
        ))}

        {EDGES.map((edge) => (
          <EdgeShape edge={edge} key={edge.label} />
        ))}

        <g>
          {(
            [
              ["request", "Request / progress"],
              ["provider", "Paid provider call"],
              ["record", "Trusted bytes / records"],
            ] as const
          ).map(([tone, label], index) => {
            const x = 20 + index * 240;
            return (
              <g key={tone}>
                <line
                  stroke={COLOURS[tone]}
                  strokeDasharray={tone === "provider" ? "5 5" : undefined}
                  strokeWidth="2.5"
                  x1={x}
                  x2={x + 30}
                  y1="472"
                  y2="472"
                />
                <text fill="var(--d-text-2)" fontSize="13" x={x + 40} y="477">
                  {label}
                </text>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}

export default ArchitectureDiagram;
