import { NextResponse } from "next/server";

import { anonymousActor } from "../../../anonymous-actor";

function error(message: string, status: number) {
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

export async function GET(request: Request) {
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("Live generation status is unavailable.", 503);
  }

  const pathname = new URL(request.url).pathname;
  const jobId = decodeURIComponent(pathname.split("/").filter(Boolean).at(-1) ?? "");
  if (!/^job_[0-9a-f]{20}$/.test(jobId)) {
    return error("The live job identifier is invalid.", 400);
  }

  const upstream = await fetch(`${apiUrl}/v1/runs/${jobId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Dara-Actor": await anonymousActor(request),
    },
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
