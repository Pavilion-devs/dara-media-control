"use client";

import { EyeOff } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { HashDisplay } from "@/components/dara/hash-display";
import { Badge, Panel, PanelBody, PanelHead } from "@/components/ui";

import { apiErrorSchema } from "../../verification-schema";
import { publicShareSchema, type PublicShare } from "../../share-schema";

function DisclosureMedia({ share }: { share: PublicShare }) {
  const asset = share.assets[0];
  // Alt text is built only from fields the redacted response permits.
  const alt = "AI-generated media disclosed through Dara";
  const frame =
    "w-full rounded-2xl border border-line bg-inset object-cover";

  if (asset.mime_type.startsWith("video/")) {
    return (
      <video aria-label={alt} className={frame} controls src={asset.url} />
    );
  }
  if (asset.mime_type.startsWith("audio/")) {
    return (
      <div className="grid content-center gap-4 rounded-2xl border border-line bg-inset p-8">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
          Audio disclosure
        </p>
        <audio aria-label={alt} className="w-full" controls src={asset.url} />
      </div>
    );
  }
  // The API supplies a short-lived B2 URL, so no static image allowlist applies.
  return <img alt={alt} className={frame} src={asset.url} />;
}

export function ShareScreen({ token }: { token: string }) {
  const [share, setShare] = useState<PublicShare | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const response = await fetch(`/api/share/${encodeURIComponent(token)}`, {
          cache: "no-store",
        });
        const body: unknown = await response.json();
        if (!response.ok) {
          const parsed = apiErrorSchema.safeParse(body);
          throw new Error(
            parsed.success
              ? parsed.data.error.message
              : "This disclosure could not be loaded.",
          );
        }
        const parsed = publicShareSchema.safeParse(body);
        if (!parsed.success) {
          throw new Error("The disclosure response did not pass validation.");
        }
        if (active) setShare(parsed.data);
      } catch (reason) {
        if (active) {
          setError(
            reason instanceof Error
              ? reason.message
              : "This disclosure could not be loaded.",
          );
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [token]);

  const asset = share?.assets[0];
  const generated = asset
    ? new Date(asset.generated_at).toLocaleString("en-GB", {
        dateStyle: "medium",
        timeStyle: "medium",
        timeZone: "UTC",
      })
    : null;

  return (
    <main className="min-h-screen bg-page text-ink">
      <div className="mx-auto w-full max-w-4xl px-6 pb-24 pt-12 md:px-8 md:pt-16">
        <Link
          className="text-xl font-semibold tracking-tight text-ink transition-opacity hover:opacity-70"
          href="/"
        >
          Da<span className="text-accent">ra</span>
        </Link>

        <header className="mb-10 mt-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-subtle">
              Client disclosure / Dara
            </p>
            <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
              Provenance proof.
            </h1>
            <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted">
              {share
                ? `Generated media disclosure · issued ${new Date(
                    share.issued_at,
                  ).toLocaleDateString("en-GB", { timeZone: "UTC" })}`
                : "Loading token-scoped disclosure…"}
            </p>
          </div>
          <Badge dot pulse={!share && !error} tone={error ? "block" : share ? "allow" : "warn"}>
            {error ? "Unavailable" : share ? "Record matched" : "Checking"}
          </Badge>
        </header>

        {error ? (
          <Panel>
            <PanelBody className="grid gap-2 p-8">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
                Disclosure unavailable
              </p>
              <p className="text-sm leading-relaxed text-muted">{error}</p>
            </PanelBody>
          </Panel>
        ) : share && asset ? (
          <div className="grid gap-6">
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <DisclosureMedia share={share} />
              <div className="grid content-start gap-5">
                <Panel>
                  <PanelHead title="Record" />
                  <PanelBody>
                    <dl className="grid gap-3">
                      {[
                        { label: "Provider", value: asset.provider },
                        { label: "Model", value: asset.model },
                        { label: "Generated", value: `${generated} UTC` },
                        {
                          label: "Verification",
                          value: "Bytes match Dara's trusted record",
                        },
                      ].map((row) => (
                        <div
                          className="flex flex-wrap items-baseline justify-between gap-3 border-b border-line pb-3 last:border-0 last:pb-0"
                          key={row.label}
                        >
                          <dt className="text-xs text-subtle">{row.label}</dt>
                          <dd className="font-mono text-sm text-ink">
                            {row.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </PanelBody>
                </Panel>

                {/* Withholding detail is the feature here, so it is stated
                    plainly rather than left looking like missing data. */}
                <div className="rounded-2xl border border-line bg-inset p-5">
                  <p className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink">
                    <EyeOff aria-hidden className="size-3.5 text-subtle" />
                    Withheld by policy
                  </p>
                  <p className="text-xs leading-relaxed text-muted">
                    {share.disclosure} The file is served from a separate
                    token-scoped object with a Genblaze redacted pointer record.
                  </p>
                </div>

                <p className="text-xs leading-relaxed text-subtle">
                  {share.trust_note}
                </p>
              </div>
            </div>

            <Panel>
              <PanelHead
                title="Shared SHA-256"
                trailing={
                  <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                    Whole file
                  </span>
                }
              />
              <PanelBody className="p-5 md:p-6">
                <HashDisplay tone="verified" value={asset.shared_sha256} />
              </PanelBody>
            </Panel>
          </div>
        ) : (
          <Panel>
            <PanelBody className="p-8">
              <p className="text-sm leading-relaxed text-muted">
                Checking the exact shared bytes against Dara&apos;s trusted
                record…
              </p>
            </PanelBody>
          </Panel>
        )}
      </div>
    </main>
  );
}
