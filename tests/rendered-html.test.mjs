import assert from "node:assert/strict";
import { createHash } from "node:crypto";
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

test("serves a healthy judge entry point and opens Studio", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  const html = await response.text();
  assert.match(html, /http-equiv="refresh"/i);
  assert.match(html, /content="0;url=\/studio"/i);
  assert.match(html, /Continue to the governed media control plane/);
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
  assert.match(html, /New generation/);
  assert.match(html, /Generate with OpenAI/);
  assert.match(html, /No recorded run is preloaded here/);
  assert.match(html, /Production workspace · B2 connected/);
  assert.doesNotMatch(html, /Replay|fixture|recorded production proof/i);
  assert.doesNotMatch(html, /codex-preview|Your site is taking shape/i);
});

test("server-renders an empty public verification flow", async () => {
  const response = await render("/verify");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Public verification/);
  assert.match(html, /Drop a file to check where it came from/);
  assert.doesNotMatch(html, /Verified demo record|Showing a committed proof/);
  assert.doesNotMatch(html, /900de07759c139b8c2175d3149e98c5ace56f80e2594def405f7e0c433e1e5ca/);
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
  assert.ok(
    verifyScreen.indexOf('fetch("/api/verify", { method: "POST", body })') <
      verifyScreen.indexOf("fetch(`/api/verify/${staged.sha256}`"),
    "full-file inspection must run before the hash-only fallback",
  );
  assert.match(nextConfig, /bodySizeLimit: "100mb"/);
  assert.match(schema, /verificationResponseSchema/);
  await access(new URL("../public/dara-verified-sample.png", import.meta.url));
  await assert.rejects(
    access(new URL("../app/_sites-preview", import.meta.url)),
  );
});

test("connects Runs to paginated live history without public fixtures", async () => {
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
  assert.match(screen, /B2 run history/);
  assert.match(screen, /No fixture history has been substituted/);
  assert.doesNotMatch(screen, /demo-runs\.json|demoSeedCorpusSchema/);
  assert.match(screen, /RegenerationAction/);
  assert.match(screen, /VersionTree/);
  assert.match(schema, /liveRunListSchema/);
  assert.match(schema, /"motion-spot"/);
  assert.match(schema, /"voiceover-pack"/);
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
  assert.equal(
    createHash("sha256").update(sample).digest("hex"),
    "900de07759c139b8c2175d3149e98c5ace56f80e2594def405f7e0c433e1e5ca",
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
  // The regression is that Vinext must not reject this 1.2 MB proof as 413 first.
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

test("accepts both legacy and production run identifiers on every run route", async () => {
  const routePaths = [
    "../app/api/runs/[id]/route.ts",
    "../app/api/runs/[id]/events/route.ts",
    "../app/api/runs/[id]/regenerate/route.ts",
    "../app/api/runs/[id]/diff/route.ts",
    "../app/api/runs/[id]/cancel/route.ts",
  ];
  const [helper, ...routes] = await Promise.all([
    readFile(new URL("../app/run-id.ts", import.meta.url), "utf8"),
    ...routePaths.map((path) => readFile(new URL(path, import.meta.url), "utf8")),
  ]);

  assert.match(helper, /A-Za-z0-9_-/);
  assert.match(helper, /\{8,80\}/);
  for (const route of routes) assert.match(route, /isRunId/);
});

test("keeps the public ledger live-only without a continuity snapshot", async () => {
  const [ledgerUi, dashboardRoute] = await Promise.all([
    readFile(
      new URL("../app/(app)/ledger/ledger-screen.tsx", import.meta.url),
      "utf8",
    ),
    readFile(new URL("../app/api/ledger/dashboard/route.ts", import.meta.url), "utf8"),
  ]);

  assert.match(ledgerUi, /\/api\/ledger\/dashboard\?project_id=/);
  assert.match(ledgerUi, /fetch\("\/api\/projects"/);
  assert.match(ledgerUi, /No recorded snapshot has been substituted/);
  assert.doesNotMatch(ledgerUi, /recordedLedgerProof|ledger-proof/);
  assert.doesNotMatch(ledgerUi, /Promise\.all\(\[\s*fetch\("\/api\/ledger/);
  assert.match(dashboardRoute, /\/v1\/ledger\/dashboard/);
});
