import { NextResponse } from "next/server";

import { getChatGPTUser } from "../../../chatgpt-auth";

export async function GET(request: Request) {
  const user = await getChatGPTUser();
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return NextResponse.json(
      { error: { code: "LEDGER_UNAVAILABLE", message: "The live ledger is not connected." } },
      { status: 503 },
    );
  }
  const query = new URL(request.url).search;
  const upstream = await fetch(`${apiUrl}/v1/ledger/dashboard${query}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Dara-Actor": user?.email ?? "public-judge",
    },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: { "content-type": "application/json" },
  });
}
