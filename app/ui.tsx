"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

type EventItem = {
  seq: number;
  time: string;
  provider: string;
  model: string;
  message: string;
  type: "normal" | "failover" | "revised" | "success";
};

const fullEvents: EventItem[] = [
  { seq: 1, time: "0.00s", provider: "dara", model: "policy/v1", message: "Pre-flight policy passed · $0.54 reserved", type: "normal" },
  { seq: 2, time: "0.08s", provider: "nvidia", model: "sd3.5-large", message: "Primary image step started", type: "normal" },
  { seq: 3, time: "1.41s", provider: "nvidia", model: "flux.1-dev", message: "sd3.5-large → flux.1-dev · provider failover", type: "failover" },
  { seq: 4, time: "4.92s", provider: "gemini", model: "2.5-flash", message: "QA score 0.68 · composition lacks product separation", type: "normal" },
  { seq: 5, time: "5.10s", provider: "dara", model: "qa/revise", message: "Prompt revised · stronger rim light, wider tonal separation", type: "revised" },
  { seq: 6, time: "9.74s", provider: "replicate", model: "flux-1.1-pro", message: "Variant 03 generated · QA score 0.89", type: "normal" },
  { seq: 7, time: "9.89s", provider: "genblaze", model: "manifest/v1", message: "Manifest verified and asset committed to B2", type: "success" },
];

const hash =
  "b7418d3e26369454a50b8c162ad80cb38c2eaf8388c5e05e63f84bf724be6a17";

const navItems = [
  ["/", "Studio"],
  ["/ledger", "Ledger"],
  ["/verify", "Verify"],
];

function Shell({
  children,
  current,
}: {
  children: React.ReactNode;
  current: string;
}) {
  return (
    <main className="shell">
      <header className="topbar">
        <Link className="brand display" href="/">
          <span className="brand-mark">D</span>
          DARA
        </Link>
        <nav className="nav" aria-label="Primary navigation">
          {navItems.map(([href, label]) => (
            <Link className={current === href ? "active" : ""} href={href} key={href}>
              {label}
            </Link>
          ))}
          <Link className={current.startsWith("/assets") ? "active" : ""} href="/assets/ast_nw_003">
            Assets
          </Link>
        </nav>
        <div className="workspace">
          <span className="live-dot" />
          Demo workspace · B2 connected
        </div>
      </header>
      {children}
    </main>
  );
}

function Badge({
  type,
  children,
}: {
  type: "allow" | "warn" | "block";
  children: React.ReactNode;
}) {
  return <span className={`policy-badge ${type}`}>{children}</span>;
}

export function HashDisplay({ value = hash }: { value?: string }) {
  return (
    <div className="hash-display mono" aria-label={`SHA-256 ${value}`}>
      {value.match(/.{1,8}/g)?.map((part, index) => (
        <span className="hash-block" key={`${part}-${index}`}>
          {part}
        </span>
      ))}
    </div>
  );
}

export function Studio() {
  const [prompt, setPrompt] = useState(
    "Hero shot of a ceramic bowl on washed linen, morning light, quiet editorial composition"
  );
  const [variants, setVariants] = useState(3);
  const [policy, setPolicy] = useState("standard");
  const [events, setEvents] = useState(fullEvents);
  const [runState, setRunState] = useState<"ready" | "running" | "done">("done");
  const [toast, setToast] = useState("");
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);

  const estimate = useMemo(() => 0.06 * variants, [variants]);
  const worstCase = estimate * 3;
  const blocked = policy === "locked" && worstCase > 0.1;

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  function runBrief() {
    if (blocked) return;
    timers.current.forEach(clearTimeout);
    setEvents([]);
    setRunState("running");
    fullEvents.forEach((event, index) => {
      const timer = setTimeout(() => {
        setEvents((current) => [...current, event]);
        if (index === fullEvents.length - 1) setRunState("done");
      }, index * 360);
      timers.current.push(timer);
    });
  }

  function approve() {
    setToast("Approved · published hash recorded");
    setTimeout(() => setToast(""), 2200);
  }

  return (
    <Shell current="/">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Generation control plane</p>
            <h1 className="page-title display">Make the work.<br />Keep the record.</h1>
            <p className="page-lede">
              Governed media pipelines with visible policy, honest cost, and provenance that survives the handoff.
            </p>
          </div>
          <Badge type={blocked ? "block" : "allow"}>
            {blocked ? "Pre-flight blocked" : "Policy active"}
          </Badge>
        </div>

        <div className="studio-grid">
          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">New brief</h2>
              <span className="mono hash-short">JOB / DRAFT</span>
            </div>
            <div className="form">
              <div className="field">
                <label htmlFor="project">Project</label>
                <select id="project" defaultValue="northwind">
                  <option value="northwind">Northwind — Q3 campaign</option>
                  <option value="atlas">Atlas Hotels — Brand film</option>
                  <option value="field">Field Notes — Product launch</option>
                </select>
              </div>
              <div className="two-col">
                <div className="field">
                  <label htmlFor="pipeline">Pipeline</label>
                  <select id="pipeline" defaultValue="still">
                    <option value="still">Still campaign</option>
                    <option value="motion">Motion spot</option>
                    <option value="voice">Voiceover pack</option>
                  </select>
                </div>
                <div className="field">
                  <label htmlFor="policy">Policy</label>
                  <select id="policy" value={policy} onChange={(e) => setPolicy(e.target.value)}>
                    <option value="permissive">Permissive</option>
                    <option value="standard">Standard client work</option>
                    <option value="locked">Locked demo · $0.10 max</option>
                  </select>
                </div>
              </div>
              <div className="field">
                <label htmlFor="prompt">Prompt</label>
                <textarea id="prompt" value={prompt} onChange={(e) => setPrompt(e.target.value)} />
              </div>
              <div className="field">
                <span className="label">Aspect ratio</span>
                <div className="segmented" role="group" aria-label="Aspect ratio">
                  <button type="button">1:1</button>
                  <button className="selected" type="button">16:9</button>
                  <button type="button">9:16</button>
                </div>
              </div>
              <div className="field">
                <label htmlFor="variants">Variants · {variants}</label>
                <input
                  id="variants"
                  max="4"
                  min="1"
                  onChange={(e) => setVariants(Number(e.target.value))}
                  type="range"
                  value={variants}
                />
              </div>
              <div className={`estimate ${blocked ? "blocked" : ""}`}>
                <div className="estimate-row">
                  <div>
                    <span className="label">Live estimate</span>
                    <small>Expected / worst case with QA retries</small>
                  </div>
                  <strong className="mono">${estimate.toFixed(2)} / ${worstCase.toFixed(2)}</strong>
                </div>
                <div className="estimate-track">
                  <div className="estimate-fill" style={{ width: `${Math.min(100, (worstCase / 2) * 100)}%` }} />
                </div>
                {blocked ? (
                  <p className="policy-message">
                    This run reserves ${worstCase.toFixed(2)}. The locked policy limit is $0.10.
                    Reduce variants to 1 or choose a policy with a higher budget.
                  </p>
                ) : null}
              </div>
              <button className="primary-btn" disabled={blocked || !prompt.trim()} onClick={runBrief} type="button">
                {blocked ? "Blocked before spend" : runState === "running" ? "Run in progress…" : "Run this brief"}
              </button>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <h2 className="panel-title">Live run · Northwind hero</h2>
              <span className={`status ${runState === "running" ? "status-running" : "status-verified"}`}>
                {runState === "running" ? "Running" : "Verified"}
              </span>
            </div>
            <div className="run-summary">
              <div className="metric"><span>Run</span><strong className="mono">01K1C4</strong></div>
              <div className="metric"><span>Actual cost</span><strong className="mono">$0.21</strong></div>
              <div className="metric"><span>QA score</span><strong className="mono">0.89</strong></div>
              <div className="metric"><span>Attempts</span><strong className="mono">2 / 3</strong></div>
            </div>
            <div className="stream" aria-live="polite">
              {events.map((event) => (
                <div className={`event mono ${event.type}`} key={event.seq}>
                  <span className="event-seq">{String(event.seq).padStart(2, "0")}</span>
                  <span className="event-time">{event.time}</span>
                  <span className="event-provider">{event.provider}</span>
                  <div>
                    {event.type === "failover" ? (
                      <span><span className="strike">sd3.5-large</span><span className="arrow">→</span>flux.1-dev · provider failover</span>
                    ) : event.message}
                    {event.type === "revised" ? (
                      <div className="revision">
                        Composition 0.72 · Product fidelity 0.64 · Brand fit 0.69<br />
                        Revision: isolate the bowl with a narrow rim light and increase foreground separation.
                      </div>
                    ) : null}
                  </div>
                  <span className={`event-tag ${event.type === "success" ? "allow" : event.type === "failover" ? "warn" : ""}`}>
                    {event.type === "success" ? "sealed" : event.type === "failover" ? "fallback" : "event"}
                  </span>
                </div>
              ))}
            </div>
            {runState === "done" ? (
              <div className="result-strip">
                <p><strong>Variant 03 is ready.</strong><br />Source and published hashes recorded separately.</p>
                <button className="secondary-btn" onClick={approve} type="button">Approve</button>
              </div>
            ) : null}
          </section>
        </div>
      </section>
      {toast ? <div className="toast" role="status">{toast}</div> : null}
    </Shell>
  );
}

const ledgerRows = [
  ["01K1C4", "Northwind — Q3", "flux-1.1-pro", "Image", "$0.21", "0.89", "Approved", 76],
  ["01K18N", "Atlas Hotels", "veo-2", "Video", "$1.84", "0.81", "Approved", 100],
  ["01K0ZR", "Field Notes", "sd3.5-large", "Image", "$0.12", "0.68", "Discarded", 44],
  ["01K0VA", "Northwind — Q3", "eleven-multilingual-v2", "Audio", "$0.09", "0.92", "Approved", 32],
  ["01JZZ8", "Atlas Hotels", "flux.1-dev", "Image", "$0.16", "0.74", "Discarded", 58],
];

export function Ledger() {
  return (
    <Shell current="/ledger">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Spend ledger</p>
            <h1 className="page-title display">The honest numbers.</h1>
            <p className="page-lede">Every attempt counts—including the work that never shipped.</p>
          </div>
          <span className="mono hash-short">JUL 01 — JUL 29, 2026</span>
        </div>
        <div className="headline-metrics">
          <div className="headline-metric">
            <span>Cost per approved asset</span>
            <strong className="mono">$0.48</strong>
            <small>Includes $2.11 in discarded attempts</small>
          </div>
          <div className="headline-metric">
            <span>Spend prevented</span>
            <strong className="mono">$37.42</strong>
            <small>14 runs blocked before provider calls</small>
          </div>
          <div className="headline-metric">
            <span>Waste ratio</span>
            <strong className="mono">18.6%</strong>
            <small>Down 4.2 points from last month</small>
          </div>
        </div>
        <div className="filterbar" aria-label="Ledger filters">
          <select aria-label="Date range" defaultValue="30"><option value="30">Last 30 days</option><option value="7">Last 7 days</option></select>
          <select aria-label="Project" defaultValue="all"><option value="all">All projects</option><option>Northwind — Q3</option></select>
          <select aria-label="Model" defaultValue="all"><option value="all">All models</option><option>flux-1.1-pro</option><option>veo-2</option></select>
        </div>
        <div className="data-panel">
          <table>
            <thead><tr><th>Run</th><th>Project</th><th>Model</th><th>Mode</th><th>Cost</th><th>QA</th><th>Status</th><th>Relative spend</th></tr></thead>
            <tbody>
              {ledgerRows.map((row) => (
                <tr key={row[0]}>
                  <td><Link className="run-link mono" href="/assets/ast_nw_003">{row[0]}</Link></td>
                  <td>{row[1]}</td><td className="mono">{row[2]}</td><td>{row[3]}</td>
                  <td className="mono">{row[4]}</td><td className="mono">{row[5]}</td>
                  <td><Badge type={row[6] === "Approved" ? "allow" : "warn"}>{row[6]}</Badge></td>
                  <td className="bar-cell mono">{row[4]}<div className="inline-bar"><span style={{ width: `${row[7]}%` }} /></div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </Shell>
  );
}

const lineage = [
  ["01 · Brief", "Dara policy engine", "Standard client work · pre-flight allow", "$0.00"],
  ["02 · Generate", "replicate / flux-1.1-pro", "16:9 · seed 803191 · guidance 3.5", "$0.14"],
  ["03 · QA", "google / gemini-2.5-flash", "Score 0.89 · passed on attempt 2", "$0.01"],
  ["04 · Publish", "Genblaze manifest / B2", "Embedded · source and published hashes indexed", "$0.00"],
];

function Lineage() {
  return (
    <div className="lineage">
      {lineage.map(([step, title, detail, cost]) => (
        <div className="lineage-node" key={step}>
          <span className="lineage-step mono">{step}</span>
          <div className="lineage-main"><strong>{title}</strong><span className="mono">{detail}</span></div>
          <span className="lineage-cost mono">{cost}</span>
        </div>
      ))}
    </div>
  );
}

export function Verify() {
  const [result, setResult] = useState(true);
  const inputRef = useRef<HTMLInputElement>(null);
  const [fileName, setFileName] = useState("northwind-hero-03.png");

  function chooseFile(file?: File) {
    if (file) setFileName(file.name);
    setResult(true);
  }

  return (
    <Shell current="/verify">
      <section className="page verify-wrap">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Public verification</p>
            <h1 className="page-title display">Check where it came from.</h1>
            <p className="page-lede">No generation provider is contacted. Dara checks the file against its trusted storage record.</p>
          </div>
        </div>
        <input
          accept="image/*,video/*,audio/*"
          hidden
          onChange={(e) => chooseFile(e.target.files?.[0])}
          ref={inputRef}
          type="file"
        />
        <button className="dropzone" onClick={() => inputRef.current?.click()} type="button">
          <span className="drop-icon">↓</span>
          <h2>Drop a file to check where it came from</h2>
          <p>or choose a file · PNG, JPG, MP4, WAV up to 50 MB</p>
        </button>
        {result ? (
          <section className="verify-result">
            <div className="hash-label">
              <div><p className="eyebrow">Published SHA-256 · {fileName}</p><h2 className="panel-title">Trusted record match</h2></div>
              <Badge type="allow">Verified</Badge>
            </div>
            <HashDisplay />
            <Lineage />
            <p className="trust-note">
              Trust boundary: tamper-evident within the issuing organisation&apos;s controlled storage.
              This is an internal accountability and good-faith disclosure record, not an adversarial authenticity proof.
            </p>
          </section>
        ) : null}
      </section>
    </Shell>
  );
}

export function AssetDetail() {
  return (
    <Shell current="/assets">
      <section className="page">
        <div className="page-heading">
          <div>
            <p className="eyebrow">Asset / AST_NW_003</p>
            <h1 className="page-title display">Northwind hero 03.</h1>
            <p className="page-lede">Approved deliverable · exact generation conditions preserved.</p>
          </div>
          <Badge type="allow">Verified</Badge>
        </div>
        <section className="panel" style={{ marginBottom: 24 }}>
          <div className="panel-head"><h2 className="panel-title">Published SHA-256</h2><span className="mono hash-short">WHOLE FILE</span></div>
          <div style={{ padding: 16 }}><HashDisplay /></div>
        </section>
        <div className="asset-grid">
          <div>
            <div className="asset-preview" role="img" aria-label="Generated Northwind campaign asset created with flux-1.1-pro" />
            <dl className="asset-meta">
              <div className="detail-row"><dt>Provider / model</dt><dd className="mono">replicate / flux-1.1-pro</dd></div>
              <div className="detail-row"><dt>Source hash</dt><dd className="mono">9f2c13ac…405d90a1</dd></div>
              <div className="detail-row"><dt>Published hash</dt><dd className="mono">b7418d3e…24be6a17</dd></div>
              <div className="detail-row"><dt>Manifest</dt><dd className="mono">b2://dara/manifests/run_01K1C4.json</dd></div>
              <div className="detail-row"><dt>Actual cost</dt><dd className="mono">$0.210000</dd></div>
            </dl>
          </div>
          <div className="panel">
            <div className="panel-head"><h2 className="panel-title">Lineage</h2><span className="mono hash-short">4 EVENTS</span></div>
            <div style={{ padding: "0 18px 24px" }}><Lineage /></div>
            <div className="panel-head"><h2 className="panel-title">Version history</h2><span className="mono hash-short">2 ATTEMPTS</span></div>
            <div className="version-row"><span className="version-index mono">01</span><span>Low product separation · discarded</span><span className="mono">QA 0.68</span><Badge type="warn">Failed</Badge></div>
            <div className="version-row"><span className="version-index mono">02</span><span>Revised rim light · published</span><span className="mono">QA 0.89</span><Badge type="allow">Approved</Badge></div>
          </div>
        </div>
      </section>
    </Shell>
  );
}

export function ShareView() {
  return (
    <main className="share-shell">
      <article className="share-card">
        <div className="page-heading">
          <div>
            <Link className="brand display" href="/" style={{ color: "var(--ink)", marginBottom: 38 }}>
              <span className="brand-mark" style={{ borderColor: "var(--ink)" }}>D</span>DARA
            </Link>
            <p className="eyebrow">Client disclosure / Northwind Foods</p>
            <h1 className="page-title display">Northwind hero 03.</h1>
            <p className="page-lede">Generated media disclosure · issued July 29, 2026</p>
          </div>
          <Badge type="allow">Record matched</Badge>
        </div>
        <div className="asset-grid">
          <div className="asset-preview" role="img" aria-label="Northwind campaign deliverable" />
          <div>
            <dl className="asset-meta">
              <div className="detail-row"><dt>Provider</dt><dd>Replicate</dd></div>
              <div className="detail-row"><dt>Model</dt><dd className="mono">flux-1.1-pro</dd></div>
              <div className="detail-row"><dt>Generated</dt><dd className="mono">2026-07-29 09:41:18 UTC</dd></div>
              <div className="detail-row"><dt>Shared hash</dt><dd className="mono">c8214fa3…8b04c35e</dd></div>
            </dl>
            <p className="redaction-note">
              Prompt and generation parameters were withheld by the project&apos;s disclosure policy.
              This shared derivative contains a separate redacted manifest and its own recorded hash.
            </p>
            <p className="trust-note">
              This disclosure is tamper-evident within Dara&apos;s controlled storage. It does not claim adversarial proof of authenticity.
            </p>
          </div>
        </div>
      </article>
    </main>
  );
}
