import { NextResponse } from "next/server";

import { isRunId } from "../../../../run-id";

import { anonymousActor } from "../../../../anonymous-actor";

export async function POST(request: Request) {
  const jobId = decodeURIComponent(
    new URL(request.url).pathname.split("/").filter(Boolean).at(-2) ?? "",
  );
  if (!isRunId(jobId)) {
    return NextResponse.json(
      { error: { code: "INVALID_RUN", message: "The run identifier is invalid.", details: {}, request_id: null } },
      { status: 400 },
    );
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return NextResponse.json(
      { error: { code: "RUN_UNAVAILABLE", message: "Live runs are not connected.", details: {}, request_id: null } },
      { status: 503 },
    );
  }
  const upstream = await fetch(
    `${apiUrl}/v1/runs/${encodeURIComponent(jobId)}/cancel`,
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
