import { NextResponse } from "next/server";

import { anonymousActor } from "../../../anonymous-actor";

const allowedQueries = new Set([
  "spend_by_model",
  "spend_by_project",
  "spend_by_month",
  "cost_per_approved_asset",
  "waste_ratio",
  "qa_pass_rate",
  "policy_savings",
]);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const queryId = url.searchParams.get("q") ?? "";
  if (!allowedQueries.has(queryId)) {
    return NextResponse.json(
      { error: { code: "UNKNOWN_LEDGER_QUERY", message: "That ledger query is not allowlisted." } },
      { status: 400 },
    );
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return NextResponse.json(
      { error: { code: "LEDGER_UNAVAILABLE", message: "The live ledger is not connected." } },
      { status: 503 },
    );
  }
  const upstream = await fetch(`${apiUrl}/v1/ledger/query${url.search}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Dara-Actor": await anonymousActor(request),
    },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
