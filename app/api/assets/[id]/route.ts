import { NextResponse } from "next/server";

function invalid(message: string, status: number) {
  return NextResponse.json(
    { error: { code: "ASSET_UNAVAILABLE", message, details: {}, request_id: null } },
    { status },
  );
}

export async function GET(request: Request) {
  const assetId = decodeURIComponent(
    new URL(request.url).pathname.split("/").filter(Boolean).at(-1) ?? "",
  );
  if (!/^[A-Za-z0-9_-]{3,100}$/.test(assetId)) {
    return invalid("The asset identifier is invalid.", 400);
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) return invalid("Live asset records are not connected.", 503);
  const upstream = await fetch(
    `${apiUrl}/v1/assets/${encodeURIComponent(assetId)}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
  );
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
