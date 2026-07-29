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

test("server-renders the Dara control plane", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Dara — Governed media generation<\/title>/i);
  assert.match(html, />DARA</);
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
  const [packageJson, verifyRoute, schema] = await Promise.all([
    readFile(new URL("../package.json", import.meta.url), "utf8"),
    readFile(new URL("../app/api/verify/route.ts", import.meta.url), "utf8"),
    readFile(new URL("../app/verification-schema.ts", import.meta.url), "utf8"),
  ]);

  assert.match(packageJson, /"zod":/);
  assert.match(verifyRoute, /DARA_API_URL/);
  assert.match(schema, /verificationResponseSchema/);
  await access(new URL("../public/dara-verified-sample.png", import.meta.url));
  await assert.rejects(
    access(new URL("../app/_sites-preview", import.meta.url)),
  );
});
