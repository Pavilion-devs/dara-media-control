import { NextResponse } from "next/server";

import { anonymousActor } from "../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 401 ? "UNAUTHORIZED" : "SHARE_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function POST(request: Request) {
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("Disclosure creation is temporarily unavailable.", 503);
  }
  const upstream = await fetch(`${apiUrl}/v1/shares`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Dara-Actor": await anonymousActor(request),
    },
    body: await request.text(),
    cache: "no-store",
  });
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
