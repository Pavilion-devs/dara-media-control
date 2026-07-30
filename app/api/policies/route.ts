import { NextResponse } from "next/server";

import { anonymousActor } from "../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: "POLICY_LIST_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function GET(request: Request) {
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("The live policy engine is not connected.", 503);
  }

  const upstream = await fetch(`${apiUrl}/v1/policies`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Dara-Actor": await anonymousActor(request),
    },
    cache: "no-store",
  });
  return new Response(await upstream.text(), {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
