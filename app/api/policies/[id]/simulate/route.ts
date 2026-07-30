import { NextResponse } from "next/server";

import { anonymousActor } from "../../../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 401 ? "UNAUTHORIZED" : "POLICY_PREVIEW_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function POST(request: Request) {
  const segments = new URL(request.url).pathname.split("/").filter(Boolean);
  const policyId = decodeURIComponent(segments.at(-2) ?? "");
  if (!/^pol_[a-z0-9_-]{2,64}$/.test(policyId)) {
    return error("The policy identifier is invalid.", 400);
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("The live policy engine is not connected.", 503);
  }
  const actor = await anonymousActor(request);

  const upstream = await fetch(
    `${apiUrl}/v1/policies/${encodeURIComponent(policyId)}/simulate`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-Dara-Actor": actor,
      },
      body: await request.text(),
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
