import { NextResponse } from "next/server";

import { anonymousActor } from "../../../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 401 ? "UNAUTHORIZED" : "LIVE_STREAM_UNAVAILABLE",
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
    return error("Live generation events are unavailable.", 503);
  }

  const segments = new URL(request.url).pathname.split("/").filter(Boolean);
  const jobId = decodeURIComponent(segments.at(-2) ?? "");
  if (!/^job_[0-9a-f]{20}$/.test(jobId)) {
    return error("The live job identifier is invalid.", 400);
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
    "X-Dara-Actor": await anonymousActor(request),
  };
  const lastEventId = request.headers.get("last-event-id");
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;

  const upstream = await fetch(`${apiUrl}/v1/runs/${jobId}/events`, {
    headers,
    cache: "no-store",
    signal: request.signal,
  });
  if (!upstream.ok || !upstream.body) {
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: {
        "content-type": upstream.headers.get("content-type") ?? "application/json",
      },
    });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Cache-Control": "no-cache, no-transform",
      "Content-Type": "text/event-stream",
      "X-Accel-Buffering": "no",
    },
  });
}
