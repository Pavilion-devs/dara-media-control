import { NextResponse } from "next/server";

import { anonymousActor } from "../../../../anonymous-actor";

export async function POST(request: Request) {
  const assetId = decodeURIComponent(
    new URL(request.url).pathname.split("/").filter(Boolean).at(-2) ?? "",
  );
  if (!/^[A-Za-z0-9_-]{3,100}$/.test(assetId)) {
    return NextResponse.json(
      { error: { code: "INVALID_ASSET", message: "The asset identifier is invalid.", details: {}, request_id: null } },
      { status: 400 },
    );
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return NextResponse.json(
      { error: { code: "ASSET_UNAVAILABLE", message: "Live asset records are not connected.", details: {}, request_id: null } },
      { status: 503 },
    );
  }
  const upstream = await fetch(
    `${apiUrl}/v1/assets/${encodeURIComponent(assetId)}/approve`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-Dara-Actor": await anonymousActor(request),
      },
      cache: "no-store",
    },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
