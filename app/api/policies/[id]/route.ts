import { NextResponse } from "next/server";

import { anonymousActor } from "../../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 400 ? "INVALID_POLICY_ID" : "POLICY_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function GET(request: Request) {
  const segments = new URL(request.url).pathname.split("/").filter(Boolean);
  const policyId = decodeURIComponent(segments.at(-1) ?? "");
  if (!/^pol_[a-z0-9_-]{2,64}$/.test(policyId)) {
    return error("The policy identifier is invalid.", 400);
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("The live policy engine is not connected.", 503);
  }

  const upstream = await fetch(
    `${apiUrl}/v1/policies/${encodeURIComponent(policyId)}`,
    {
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
