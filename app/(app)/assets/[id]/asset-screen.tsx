import { HashDisplay } from "@/components/dara/hash-display";
import { LineageSpine, type LineageNode } from "@/components/dara/lineage-spine";
import { Badge, CopyRow, Panel, PanelBody, PanelHead } from "@/components/ui";
import type { AssetRecord } from "../../../asset-schema";

/**
 * The recorded OpenAI → Genblaze → B2 proof. Held as a constant because this is
 * evidence from a specific production run, not a synthetic sample.
 */
const seededAsset = {
  id: "B9885F41",
  publishedSha256:
    "900de07759c139b8c2175d3149e98c5ace56f80e2594def405f7e0c433e1e5ca",
  sourceSha256:
    "83c597a8937c372ae6f606d3ab974d986aa434cf0d0bfa0f538be11dbed35eeb",
  provider: "openai-dalle",
  model: "gpt-image-2",
  manifestKey: "d7bc702cafdbbe4b48eef3df2e4c92c0e6b0e2eb4d16b8a72086a4f3ba116f58",
  latency: "Recorded live",
  previewUrl: "/dara-verified-sample.png",
  mimeType: "image/png",
};

function AssetPreview({
  mimeType,
  model,
  previewUrl,
  provider,
}: {
  mimeType: string;
  model: string;
  previewUrl: string;
  provider: string;
}) {
  const label = `Dara provenance proof generated with ${provider} ${model}`;
  const frame =
    "aspect-[4/3] w-full rounded-2xl border border-line bg-inset object-cover";

  if (mimeType.startsWith("video/")) {
    return <video aria-label={label} className={frame} controls src={previewUrl} />;
  }
  if (mimeType.startsWith("audio/")) {
    return (
      <div className="grid min-h-48 content-center gap-4 rounded-2xl border border-line bg-inset p-8">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
          Audio provenance proof
        </p>
        <audio aria-label={label} className="w-full" controls src={previewUrl} />
      </div>
    );
  }
  return <img alt={label} className={frame} src={previewUrl} />;
}

const seededLineage: LineageNode[] = [
  {
    key: "brief",
    step: "01 · brief",
    title: "Dara policy engine",
    detail: "Standard client work · pre-flight allow",
    trailing: "$0.00",
  },
  {
    key: "generate",
    step: "02 · generate",
    title: "openai-dalle / gpt-image-2",
    detail: "1024×1024 · low quality · PNG",
    trailing: "$0.01*",
  },
  {
    key: "record",
    step: "03 · record",
    title: "Genblaze manifest / B2",
    detail: "Source hash and canonical manifest verified",
    trailing: "$0.00",
  },
  {
    key: "publish",
    step: "04 · publish",
    title: "Dara publish / B2",
    detail: "Embedded derivative and published hash indexed",
    trailing: "$0.00",
  },
];

export function AssetScreen({ id, record }: { id: string; record: AssetRecord | null }) {
  const step = record?.verification?.manifest?.steps[0];
  const asset = record
    ? {
        id: record.asset.asset_id,
        publishedSha256: record.asset.published_sha256 ?? record.asset.source_sha256,
        sourceSha256: record.asset.source_sha256,
        provider: step?.provider ?? "recorded provider",
        model: step?.model ?? "recorded model",
        manifestKey: record.verification?.manifest?.canonical_hash ?? record.asset.run_id,
        latency: `${record.asset.cost_basis} cost · $${record.asset.cost_usd}`,
        previewUrl: record.asset_url,
        mimeType: record.asset.mime_type,
      }
    : seededAsset;
  const lineage: LineageNode[] = record?.verification
    ? record.verification.lineage.map((item, index) => ({
        key: `${item.run_id}-${index}`,
        step: `${String(index + 1).padStart(2, "0")} · ${item.relationship}`,
        title: `${item.provider ?? "Parent run"} / ${item.model ?? "record"}`,
        detail: item.run_id,
        trailing: new Date(item.at).toISOString().slice(0, 10),
      }))
    : seededLineage;
  return (
    <div className="min-w-0 grid gap-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="mb-2 font-mono text-xs uppercase tracking-widest text-subtle">
            Asset / {id}
          </p>
          <h1 className="text-4xl font-semibold tracking-tighter text-ink md:text-5xl">
            Dara provenance proof.
          </h1>
          <p className="mt-3 max-w-xl text-base leading-relaxed text-muted">
            Approved deliverable · exact provider record preserved.
          </p>
        </div>
        <Badge dot tone="allow">
          Verified
        </Badge>
      </div>

      {/* The hash is the signature element, so it leads at display size. */}
      <Panel>
        <PanelHead
          title="Published SHA-256"
          trailing={
            <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
              Whole file
            </span>
          }
        />
        <PanelBody className="p-5 md:p-6">
          <HashDisplay tone="verified" value={asset.publishedSha256} />
          <p className="mt-4 text-xs leading-relaxed text-subtle">
            Embedding changes a file, so the Genblaze source hash and this
            delivered hash are deliberately different. Dara records both.
          </p>
        </PanelBody>
      </Panel>

      <div className="min-w-0 grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="min-w-0 grid content-start gap-6">
          {/* B2 signs delivered asset URLs at runtime; no static allowlist applies. */}
          <AssetPreview
            mimeType={asset.mimeType}
            model={asset.model}
            previewUrl={asset.previewUrl}
            provider={asset.provider}
          />
          <Panel>
            <PanelHead title="Record" />
            <PanelBody className="grid gap-4">
              <dl className="min-w-0 grid gap-3">
                {[
                  { label: "Provider / model", value: `${asset.provider} / ${asset.model}` },
                  { label: "Provider latency", value: asset.latency },
                ].map((row) => (
                  <div
                    className="flex items-baseline justify-between gap-4 border-b border-line pb-3 last:border-0 last:pb-0"
                    key={row.label}
                  >
                    <dt className="text-xs text-subtle">{row.label}</dt>
                    <dd className="min-w-0 truncate font-mono text-sm text-ink">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
              <CopyRow
                display={`${asset.sourceSha256.slice(0, 8)}…${asset.sourceSha256.slice(-8)}`}
                label="Source hash (pre-embed)"
                value={asset.sourceSha256}
              />
              <CopyRow
                display={`${asset.publishedSha256.slice(0, 8)}…${asset.publishedSha256.slice(-8)}`}
                label="Published hash (delivered)"
                value={asset.publishedSha256}
              />
              <CopyRow label="Manifest hash" value={asset.manifestKey} />
            </PanelBody>
          </Panel>
        </div>

        <div className="min-w-0 grid content-start gap-6">
          <Panel>
            <PanelHead
              title="Lineage"
              trailing={
                <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                  {lineage.length} events
                </span>
              }
            />
            <PanelBody className="p-5 md:p-6">
              <LineageSpine nodes={lineage} />
            </PanelBody>
          </Panel>

          <Panel>
            <PanelHead
              title="Version history"
              trailing={
                <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">
                  1 recorded run
                </span>
              }
            />
            <div className="flex items-center gap-4 px-5 py-4">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg border border-line font-mono text-xs text-subtle">
                01
              </span>
              <span className="min-w-0 flex-1 text-sm text-ink">
                Generated, embedded, and published
              </span>
              <span className="font-mono text-xs text-subtle">Hash OK</span>
              <Badge tone="allow">Approved</Badge>
            </div>
          </Panel>

          <p className="text-xs leading-relaxed text-subtle">
            * Conservative low-quality policy reservation. The provider did not
            return a settled cost in the recorded manifest.
          </p>
        </div>
      </div>
    </div>
  );
}
