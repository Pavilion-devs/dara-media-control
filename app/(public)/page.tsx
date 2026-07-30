import {
  ArrowRight,
  BarChart3,
  FileCheck2,
  Fingerprint,
  Layers,
  Receipt,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { Badge, buttonClass } from "@/components/ui";

const steps = [
  {
    title: "Policy clears the brief",
    body: "Cost is estimated from the model registry and checked against budget before a provider is ever called. A run that would overspend is rejected at zero cost.",
  },
  {
    title: "The pipeline runs under watch",
    body: "Every step streams. Fallback routes, QA revisions, and failed attempts are all preserved and linked by parent run, so the version tree shows the real history.",
  },
  {
    title: "The record outlives the file",
    body: "The manifest is embedded, both hashes are indexed in B2, and immutable Parquet accounts for the work — including the attempts that never shipped.",
  },
];

const pillars = [
  {
    icon: FileCheck2,
    label: "Verify",
    body: "Drop in any file. Dara extracts the embedded manifest, checks its canonical integrity, and compares the bytes against the trusted published record.",
    figure: "Public",
    caption: "NO PROVIDER CALL",
    featured: true,
  },
  {
    icon: ShieldCheck,
    label: "Govern",
    body: "Typed policies enforced at four points — pre-flight, before every provider step, after QA, and after embedding but before publication.",
    figure: "Pre-spend",
    caption: "BLOCKED AT ZERO COST",
  },
  {
    icon: Receipt,
    label: "Account",
    body: "Immutable per-run Parquet in B2, queried in place by DuckDB. Failed, rejected, and policy-blocked work stays visible.",
    figure: "Honest",
    caption: "COST PER APPROVED ASSET",
  },
];

export default function LandingPage() {
  return (
    <main className="mx-auto w-full max-w-[1800px] px-6 pb-20 md:px-12">
      {/* Hero */}
      <section className="pt-12 md:pt-20">
        <div className="mb-12 grid grid-cols-1 items-end gap-10 lg:grid-cols-12">
          <div className="lg:col-span-7">
            <Badge className="mb-6" dot pulse tone="allow">
              Live on Backblaze B2
            </Badge>
            <h1 className="text-5xl font-semibold leading-[1.05] tracking-tighter md:text-7xl">
              Make the work.
              <br />
              Keep the <span className="text-accent">record</span>.
            </h1>
          </div>
          <div className="flex flex-col items-start lg:col-span-5 lg:items-end lg:pl-10">
            <p className="mb-8 max-w-sm text-lg font-medium text-muted lg:text-right md:text-xl">
              The control plane for AI-generated media: governed pipelines,
              verifiable provenance, and a spend ledger that counts what never
              shipped.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <Link
                className={buttonClass({ pill: true, size: "lg" })}
                href="/studio"
              >
                Open Studio
                <span className="flex size-7 items-center justify-center rounded-full bg-page/20">
                  <ArrowRight aria-hidden className="size-4" />
                </span>
              </Link>
              <Link
                className={buttonClass({
                  pill: true,
                  size: "lg",
                  variant: "secondary",
                })}
                href="/verify"
              >
                Verify a file
              </Link>
            </div>
          </div>
        </div>

        {/* Hash plate — the signature element, stated up front. */}
        <div className="relative overflow-hidden rounded-[2rem] border border-line bg-inset p-8 md:rounded-[3rem] md:p-16">
          <div
            aria-hidden
            className="pointer-events-none absolute -right-24 -top-24 size-[420px] rounded-full bg-accent/10 blur-[100px]"
          />
          <div className="relative">
            <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                Published SHA-256 · whole file
              </span>
              <Badge dot tone="allow">
                Trusted match
              </Badge>
            </div>
            <p className="grid grid-cols-2 gap-x-6 gap-y-2 font-mono text-lg tracking-tight text-ink sm:grid-cols-4 md:text-2xl lg:grid-cols-8">
              {"efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25"
                .match(/.{1,8}/g)
                ?.map((block) => (
                  <span key={block}>{block}</span>
                ))}
            </p>
            <p className="mt-8 max-w-xl text-sm leading-relaxed text-subtle">
              Genblaze&apos;s source hash and the delivered file&apos;s hash are
              deliberately different — embedding changes the bytes. Dara records
              both and never pretends they should match.
            </p>
          </div>
        </div>
      </section>

      <div aria-hidden className="my-16 h-px bg-line" />

      {/* How it works */}
      <section className="relative overflow-hidden rounded-[2rem] bg-[#111111] p-8 text-white md:rounded-[3rem] md:p-16 lg:p-24">
        <div
          aria-hidden
          className="pointer-events-none absolute right-0 top-0 size-[500px] -translate-y-1/2 translate-x-1/2 rounded-full bg-indigo-900/25 blur-[100px]"
        />
        <div className="relative grid grid-cols-1 gap-16 lg:grid-cols-2">
          <div className="flex flex-col justify-center">
            <div className="mb-8 flex items-center gap-2 text-sm font-medium uppercase tracking-wide text-neutral-400">
              <span
                aria-hidden
                className="size-2 animate-pulse rounded-full bg-indigo-500"
              />
              How it works
            </div>
            <h2 className="mb-8 text-5xl font-semibold leading-tight tracking-tighter md:text-7xl">
              Govern.
              <span className="flex items-center gap-4 text-neutral-500">
                <Layers aria-hidden className="size-12 md:size-16" strokeWidth={1.5} />
                Generate.
              </span>
              Account.
            </h2>
            <p className="max-w-md text-xl leading-relaxed text-neutral-400 md:text-2xl">
              Generation tooling is excellent. The operational layer under it
              did not exist — so Dara makes provenance and cost part of the
              media supply chain.
            </p>
          </div>
          <div className="rounded-2xl border border-neutral-800 bg-[#1A1A1A] p-6 shadow-2xl md:p-8">
            <div className="grid gap-6">
              {steps.map((step, index) => (
                <div className="flex items-start gap-4" key={step.title}>
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-full border border-indigo-500/30 bg-indigo-500/20 text-sm font-bold text-indigo-400">
                    {index + 1}
                  </span>
                  <div>
                    <h3 className="mb-1 font-semibold text-white">
                      {step.title}
                    </h3>
                    <p className="text-sm leading-relaxed text-neutral-500">
                      {step.body}
                    </p>
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-8 rounded-xl border border-neutral-700 bg-[#222] p-6">
              <div className="mb-4 flex justify-between text-xs font-medium text-neutral-500">
                <span className="text-white">One bucket, distinct roles</span>
                <span>Backblaze B2</span>
              </div>
              <p className="mb-2 text-center font-mono text-3xl font-light tracking-widest text-white md:text-4xl">
                LEDGER
              </p>
              <p className="mb-6 text-center text-sm text-neutral-500">
                Immutable Parquet, queried in place by DuckDB
              </p>
              <Link
                className="block w-full rounded-full bg-white py-3.5 text-center text-sm font-bold text-black transition-colors hover:bg-neutral-200"
                href="/ledger"
              >
                See the numbers
              </Link>
            </div>
          </div>
        </div>
      </section>

      <div aria-hidden className="my-20 h-px bg-line" />

      {/* Pillars */}
      <section>
        <div className="mb-12 max-w-2xl">
          <p className="mb-4 text-xs font-semibold uppercase tracking-widest text-subtle">
            What Dara does
          </p>
          <h2 className="text-4xl font-semibold leading-[1.1] tracking-tighter text-ink md:text-5xl lg:text-6xl">
            Answers you can hand to a client.
          </h2>
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {pillars.map((pillar) => (
            <article
              className={`flex min-h-80 flex-col rounded-3xl p-8 transition-colors ${
                pillar.featured
                  ? "bg-accent/10"
                  : "bg-inset hover:bg-line/40"
              }`}
              key={pillar.label}
            >
              <div className="mb-2 flex items-center gap-2">
                <pillar.icon
                  aria-hidden
                  className={`size-5 ${pillar.featured ? "text-accent-ink" : "text-subtle"}`}
                />
                <span className="text-sm font-medium text-muted">
                  {pillar.label}
                </span>
              </div>
              <p className="mt-2 max-w-xs text-sm leading-relaxed text-subtle">
                {pillar.body}
              </p>
              <p className="mt-auto pt-8 text-5xl font-semibold tracking-tighter text-ink md:text-6xl">
                {pillar.figure}
                <span className="ml-2 align-middle text-xs font-medium tracking-normal text-subtle opacity-70">
                  {pillar.caption}
                </span>
              </p>
            </article>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mt-20">
        <div className="relative overflow-hidden rounded-[2.5rem] bg-[#111111] px-8 py-20 text-center md:py-32">
          <div
            aria-hidden
            className="pointer-events-none absolute left-1/2 top-1/2 size-[600px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-indigo-900/25 blur-[120px]"
          />
          <div className="relative mx-auto flex max-w-3xl flex-col items-center">
            <h2 className="mb-8 text-5xl font-semibold leading-none tracking-tighter text-white md:text-7xl lg:text-8xl">
              Keep the
              <br />
              receipts.
            </h2>
            <p className="mb-10 max-w-lg text-lg leading-relaxed text-neutral-400 md:text-xl">
              No account required. The Studio demo replays a committed corpus at
              zero cost, and Verify never contacts a provider.
            </p>
            <div className="flex w-full flex-col items-center justify-center gap-4 md:flex-row">
              <Link
                className="min-w-52 rounded-full bg-white px-10 py-4 text-base font-bold text-black transition-colors hover:bg-neutral-200"
                href="/studio"
              >
                Open Studio
              </Link>
              <Link
                className="min-w-52 rounded-full border border-neutral-700 px-10 py-4 text-base font-semibold text-white transition-colors hover:border-white"
                href="/verify"
              >
                Verify a file
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-20 border-t border-line pt-12">
        <p className="select-none whitespace-nowrap text-center text-[15vw] font-bold uppercase leading-[0.8] tracking-tighter text-ink">
          Dara
        </p>
        <div className="mt-8 flex flex-col items-start justify-between gap-6 pb-12 md:flex-row md:items-center">
          <div className="flex gap-3">
            <span className="flex size-12 items-center justify-center rounded-full border border-line bg-inset">
              <Fingerprint aria-hidden className="size-5 text-muted" />
            </span>
            <span className="flex size-12 items-center justify-center rounded-full border border-line bg-inset">
              <BarChart3 aria-hidden className="size-5 text-muted" />
            </span>
          </div>
          <p className="text-sm font-medium text-subtle">
            Tamper-evident within the issuing organisation&apos;s storage. Not
            an adversarial authenticity proof.
          </p>
          <p className="text-sm font-medium text-faint">
            Built on Genblaze + Backblaze B2
          </p>
        </div>
      </footer>
    </main>
  );
}
