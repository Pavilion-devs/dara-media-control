import { cn } from "../ui/cn";

const PHASES = [
  {
    x: 34,
    step: "01",
    title: "Request",
    detail: "brief · project · policy",
    tone: "accent",
  },
  {
    x: 198,
    step: "02",
    title: "Pre-flight",
    detail: "estimate · check · reserve",
    tone: "accent",
  },
  {
    x: 362,
    step: "03",
    title: "Persist queued",
    detail: "job + policy decision → B2",
    tone: "record",
  },
  {
    x: 526,
    step: "04",
    title: "Provider loop",
    detail: "generate · QA · revise",
    tone: "provider",
  },
  {
    x: 690,
    step: "05",
    title: "Publish gate",
    detail: "approve · embed · re-extract",
    tone: "accent",
  },
  {
    x: 854,
    step: "06",
    title: "Commit evidence",
    detail: "bytes · manifest · indexes",
    tone: "record",
  },
  {
    x: 1018,
    step: "07",
    title: "Account",
    detail: "immutable Parquet · settle",
    tone: "record",
  },
] as const;

const COLOURS = {
  accent: "var(--d-accent)",
  provider: "var(--d-pending)",
  record: "var(--d-verified)",
} as const;

function Phase({ phase }: { phase: (typeof PHASES)[number] }) {
  const colour = COLOURS[phase.tone];
  return (
    <g>
      <rect
        fill="var(--d-surface)"
        height="108"
        rx="12"
        stroke={colour}
        strokeWidth="1.4"
        width="144"
        x={phase.x}
        y="94"
      />
      <circle fill={colour} r="15" cx={phase.x + 24} cy="94" />
      <text
        fill="var(--d-accent-contrast)"
        fontSize="13"
        fontWeight="750"
        textAnchor="middle"
        x={phase.x + 24}
        y="98"
      >
        {phase.step}
      </text>
      <text fill="var(--d-text)" fontSize="17.6" fontWeight="650" x={phase.x + 16} y="132">
        {phase.title}
      </text>
      <foreignObject height="52" width="116" x={phase.x + 16} y="144">
        <div
          style={{
            color: "var(--d-text-3)",
            fontFamily: "var(--font-sans)",
            fontSize: 10,
            lineHeight: 1.45,
          }}
        >
          {phase.detail}
        </div>
      </foreignObject>
    </g>
  );
}

export function GenerationFlowDiagram({ className }: { className?: string }) {
  return (
    <div className={cn(// Escape the prose column so the figure gets the full content width.
        "col-start-1! col-end-4! w-full rounded-2xl border border-line bg-surface p-4", className)}>
      <svg
        aria-labelledby="generation-flow-title generation-flow-description"
        className="block h-auto w-full"
        fontFamily="var(--font-sans)"
        role="img"
        viewBox="0 0 1200 342"
      >
        <title id="generation-flow-title">Governed generation request flow</title>
        <desc id="generation-flow-description">
          A request is evaluated and reserved before a durable queued record is written.
          Provider and quality loops run before a publication gate commits evidence and
          immutable accounting. A blocked request records zero provider spend.
        </desc>
        <defs>
          <marker
            id="generation-arrow"
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
            id="generation-arrow-accent"
            markerHeight="7"
            markerUnits="strokeWidth"
            markerWidth="7"
            orient="auto"
            refX="6"
            refY="3.5"
          >
            <path d="M 0 0 L 7 3.5 L 0 7 z" fill="var(--d-accent)" />
          </marker>
          <marker
            id="generation-arrow-block"
            markerHeight="7"
            markerUnits="strokeWidth"
            markerWidth="7"
            orient="auto"
            refX="6"
            refY="3.5"
          >
            <path d="M 0 0 L 7 3.5 L 0 7 z" fill="var(--d-blocked)" />
          </marker>
        </defs>

        <text fill="var(--d-text-3)" fontSize="14.2" fontWeight="700" letterSpacing="0.12em" x="34" y="38">
          AUTHORITATIVE RUN LIFECYCLE
        </text>
        <text fill="var(--d-text-2)" fontSize="16.2" x="34" y="62">
          Paid work cannot begin until policy admits the worst-case reservation.
        </text>

        {PHASES.slice(0, -1).map((phase, index) => {
          const next = PHASES[index + 1];
          return (
            <line
              key={`${phase.step}-${next.step}`}
              markerEnd="url(#generation-arrow)"
              stroke="var(--d-line-strong)"
              strokeWidth="1.5"
              x1={phase.x + 144}
              x2={next.x - 8}
              y1="148"
              y2="148"
            />
          );
        })}
        {PHASES.map((phase) => (
          <Phase key={phase.step} phase={phase} />
        ))}

        <path
          d="M 270 202 C 270 245 318 258 368 258"
          fill="none"
          markerEnd="url(#generation-arrow-block)"
          stroke="var(--d-blocked)"
          strokeWidth="1.5"
        />
        <rect
          fill="color-mix(in srgb, var(--d-blocked) 7%, var(--d-surface))"
          height="54"
          rx="10"
          stroke="var(--d-blocked)"
          width="242"
          x="376"
          y="232"
        />
        <text fill="var(--d-blocked-ink)" fontSize="15.5" fontWeight="650" x="392" y="253">
          BLOCK · persist decision and saved cost
        </text>
        <text fill="var(--d-text-3)" fontSize="13.5" x="392" y="271">
          provider calls: 0 · settled spend: $0
        </text>

        <path
          d="M 1090 94 C 1090 48 160 48 160 94"
          fill="none"
          markerEnd="url(#generation-arrow-accent)"
          stroke="var(--d-accent)"
          strokeDasharray="5 5"
          strokeWidth="1.4"
        />
        <rect fill="var(--d-surface)" height="20" rx="6" width="176" x="514" y="39" />
        <text fill="var(--d-accent-ink)" fontSize="13.5" fontWeight="650" textAnchor="middle" x="602" y="53">
          SSE progress · terminal receipt
        </text>

        <g>
          <line stroke="var(--d-accent)" strokeWidth="2" x1="34" x2="62" y1="319" y2="319" />
          <text fill="var(--d-text-2)" fontSize="14.2" x="72" y="323">control decision</text>
          <line stroke="var(--d-pending)" strokeDasharray="5 5" strokeWidth="2" x1="210" x2="238" y1="319" y2="319" />
          <text fill="var(--d-text-2)" fontSize="14.2" x="248" y="323">paid work</text>
          <line stroke="var(--d-verified)" strokeWidth="2" x1="350" x2="378" y1="319" y2="319" />
          <text fill="var(--d-text-2)" fontSize="14.2" x="388" y="323">durable record</text>
        </g>
      </svg>
    </div>
  );
}

export default GenerationFlowDiagram;
