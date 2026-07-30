import { NextResponse } from "next/server";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 400 ? "INVALID_HASH" : "VERIFICATION_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

export async function GET(request: Request) {
  const sha256 = decodeURIComponent(
    new URL(request.url).pathname.split("/").filter(Boolean).at(-1) ?? "",
  ).toLowerCase();
  if (!/^[0-9a-f]{64}$/.test(sha256)) {
    return error("SHA-256 must be exactly 64 hexadecimal characters.", 400);
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  if (!apiUrl) {
    return error("Live verification is not connected on this deployment.", 503);
  }
  const upstream = await fetch(`${apiUrl}/v1/verify/${sha256}`, {
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
