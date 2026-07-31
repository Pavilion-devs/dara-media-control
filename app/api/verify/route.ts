import { NextResponse } from "next/server";

import { clientAddress } from "../../anonymous-actor";

function unavailable() {
  return NextResponse.json(
    {
      error: {
        code: "STORAGE_UNAVAILABLE",
        message:
          "Live verification is not connected on this deployment yet. The verified demo record remains available.",
        details: {},
        request_id: null,
      },
    },
    { status: 503 },
  );
}

export async function POST(request: Request) {
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  if (!apiUrl) return unavailable();

  if (!request.body) {
    return NextResponse.json(
      {
        error: {
          code: "INVALID_REQUEST",
          message: "Choose a file to verify.",
          details: {},
          request_id: null,
        },
      },
      { status: 400 },
    );
  }
  const contentType = request.headers.get("content-type");
  const forwardedAddress = clientAddress(request);
  const init: RequestInit & { duplex: "half" } = {
    method: "POST",
    body: request.body,
    cache: "no-store",
    duplex: "half",
    headers: {
      ...(contentType ? { "Content-Type": contentType } : {}),
      "X-Forwarded-For": forwardedAddress,
    },
  };
  const upstream = await fetch(`${apiUrl}/v1/verify`, init);
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
