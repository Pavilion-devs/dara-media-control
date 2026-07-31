import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import test from "node:test";

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set(
    "test",
    `${pathname}-${process.pid}-${Date.now()}`,
  );
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );
}

test("routes the judge entry point directly to Studio", async () => {
  const response = await render();
  assert.equal(response.status, 307);
  assert.equal(new URL(response.headers.get("location")).pathname, "/studio");
});

test("server-renders the public product overview", async () => {
  const response = await render("/about");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Dara — Governed media generation<\/title>/i);
  assert.match(html, /Make the work\./);
  assert.match(html, /Keep the/);
  assert.match(html, /Open Studio/);
  assert.match(html, /Verify a file/);
  // The landing must state the trust boundary rather than overclaim.
  assert.match(html, /Not an adversarial authenticity proof/);
  // No operator chrome or seeded run internals leak onto the public page.
  assert.doesNotMatch(html, /Demo workspace · B2 connected/);
  assert.doesNotMatch(html, /Seeded QA loop fixture/);
});

test("server-renders the Dara control plane", async () => {
  const response = await render("/studio");
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Dara — Governed media generation<\/title>/i);
  assert.match(html, /Make the work\./);
  assert.match(html, /Keep the record\./);
  assert.match(html, /Checking policy/);
  assert.match(html, /B2 connected/);
  assert.match(html, /Seeded QA loop fixture · deterministic/);
  assert.match(html, /mock-image-v1/);
  assert.match(html, /Vision QA scored 0.58/);
  assert.match(html, /Prompt revised; second attempt linked by parent_run_id/);
  assert.match(html, />13</);
  assert.match(html, /committed seed runs/);
  assert.match(html, /Production proofs and fixtures are never conflated/);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i);
});

test("server-renders the real verified demo record", async () => {
  const response = await render("/verify");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Public verification/);
  assert.match(html, /Drop a file to check where it came from/);
  assert.match(html, /Verified demo record/);
  assert.match(html, /Trusted published record match/);
  assert.match(
    html,
    /efaf24d3c4cbeeb2497acd5fcba1e485be529a0ece944190c4caef8720244c25/,
  );
  assert.match(html, /openai-dalle/);
  assert.match(html, /gpt-image-2/);
  assert.match(html, /Not an adversarial authenticity proof/);
});

test("server-renders the token-scoped disclosure shell without private demo content", async () => {
  const response = await render(
    "/share/shr_0123456789abcdefghijklmnopqrstuvwxyzABCDE",
  );
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /Client disclosure/);
  assert.match(html, /Loading token-scoped disclosure/);
  assert.doesNotMatch(html, /Northwind campaign deliverable/);
  assert.doesNotMatch(html, /A cinematic|prompt/i);
});

test("ships product assets and response validation without starter files", async () => {
  const [
    packageJson,
    verifyRoute,
    verifyLookupRoute,
    verifyScreen,
    schema,
    nextConfig,
  ] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../app/api/verify/route.ts", import.meta.url), "utf8"),
    readFile(
      new URL("../app/api/verify/[sha256]/route.ts", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../app/(public)/verify/verify-screen.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/verification-schema.ts", import.meta.url), "utf8"),
    readFile(new URL("../next.config.ts", import.meta.url), "utf8"),
  ]);

  assert.match(packageJson, /"zod":/);
  assert.match(verifyRoute, /DARA_API_URL/);
  assert.match(verifyRoute, /body: request\.body/);
  assert.doesNotMatch(verifyRoute, /request\.formData/);
  assert.match(verifyLookupRoute, /\/v1\/verify\/\$\{sha256\}/);
  assert.match(verifyScreen, /fetch\(`\/api\/verify\/\$\{staged\.sha256\}`/);
  assert.match(nextConfig, /bodySizeLimit: "100mb"/);
  assert.match(schema, /verificationResponseSchema/);
  await access(new URL("../public/dara-verified-sample.png", import.meta.url));
  await assert.rejects(
    access(new URL("../app/_sites-preview", import.meta.url)),
  );
});

test("connects Runs to paginated live history without blending fixtures", async () => {
  const [route, screen, schema, regeneration, versionTree] = await Promise.all([
    readFile(new URL("../app/api/runs/route.ts", import.meta.url), "utf8"),
    readFile(
      new URL("../app/(app)/runs/runs-screen.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/run-schema.ts", import.meta.url), "utf8"),
    readFile(
      new URL("../components/dara/regeneration-action.tsx", import.meta.url),
      "utf8",
    ),
    readFile(
      new URL("../components/dara/version-tree.tsx", import.meta.url),
      "utf8",
    ),
  ]);

  assert.match(route, /export async function GET/);
  assert.match(route, /\/v1\/runs\$\{query\}/);
  assert.match(screen, /fetch\("\/api\/runs\?limit=50"/);
  assert.match(screen, /Live B2 history/);
  assert.match(screen, /never blended into these committed totals/);
  assert.match(screen, /RegenerationAction/);
  assert.match(screen, /VersionTree/);
  assert.match(schema, /liveRunListSchema/);
  assert.match(regeneration, /\/regenerate/);
  assert.match(regeneration, /\/diff\?against=/);
  assert.match(regeneration, /Confirm · reserve/);
  assert.match(regeneration, /Recorded parameter diff/);
  assert.match(versionTree, /parentId/);
});

test("allows the shipped verification proof through the web request boundary", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `verify-upload-${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const sample = await readFile(
    new URL("../public/dara-verified-sample.png", import.meta.url),
  );
  const body = new FormData();
  body.set("file", new Blob([sample], { type: "image/png" }), "proof.png");

  const response = await worker.fetch(
    new Request("http://localhost/api/verify", { method: "POST", body }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  // No API URL is configured in this isolated render, so the route returns 503.
  // The regression is that Vinext must not reject this 1.1 MB proof as 413 first.
  assert.equal(response.status, 503);
});

test("keeps every browser-facing data route public and anonymously attributed", async () => {
  const routePaths = [
    "../app/api/ledger/dashboard/route.ts",
    "../app/api/ledger/query/route.ts",
    "../app/api/ledger/summary/route.ts",
    "../app/api/policies/[id]/simulate/route.ts",
    "../app/api/runs/route.ts",
    "../app/api/runs/[id]/route.ts",
    "../app/api/runs/[id]/regenerate/route.ts",
    "../app/api/runs/[id]/diff/route.ts",
    "../app/api/runs/[id]/events/route.ts",
    "../app/api/shares/route.ts",
  ];
  const sources = await Promise.all(
    routePaths.map((path) => readFile(new URL(path, import.meta.url), "utf8")),
  );

  for (const source of sources) {
    assert.doesNotMatch(source, /getChatGPTUser|Sign in to/);
    assert.match(source, /anonymousActor/);
  }

  const packageJson = await readFile(
    new URL("../package.json", import.meta.url),
    "utf8",
  );
  assert.match(
    packageJson,
    /"test": "npm run typecheck && npm run build && node --test/,
  );
});

test("ships the verified ledger continuity snapshot without invented spend", async () => {
  const [proof, ledgerUi, dashboardRoute] = await Promise.all([
    readFile(new URL("../app/ledger-proof.ts", import.meta.url), "utf8"),
    readFile(
      new URL("../app/(app)/ledger/ledger-screen.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/api/ledger/dashboard/route.ts", import.meta.url), "utf8"),
  ]);

  assert.match(proof, /run_count: 9/);
  assert.match(proof, /approved_assets: 6/);
  assert.match(proof, /total_spend_usd: "0\.095000"/);
  assert.match(proof, /spend_prevented_usd: "0\.015000"/);
  assert.match(proof, /\["gpt-image-2", "openai", 9, "0\.095000", "0\.013571"\]/);
  assert.match(proof, /\["prj_t24_proof", 2, 2, null\]/);
  assert.match(ledgerUi, /fetch\("\/api\/ledger\/dashboard"/);
  assert.doesNotMatch(ledgerUi, /Promise\.all\(\[\s*fetch\("\/api\/ledger/);
  assert.match(dashboardRoute, /\/v1\/ledger\/dashboard/);
});
