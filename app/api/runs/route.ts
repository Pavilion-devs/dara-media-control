import { NextResponse } from "next/server";

import { getChatGPTUser } from "../../chatgpt-auth";

function unavailable(message: string, status = 503) {
  return NextResponse.json(
    {
      error: {
        code: status === 401 ? "UNAUTHORIZED" : "LIVE_GENERATION_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function POST(request: Request) {
  const user = await getChatGPTUser();
  if (!user) {
    return unavailable("Sign in to start a live Dara generation.", 401);
  }

  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return unavailable(
      "Live generation is not connected on this deployment. Demo replay remains available.",
    );
  }

  const upstream = await fetch(`${apiUrl}/v1/runs`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      "X-Dara-Actor": user.email,
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
