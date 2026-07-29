import { NextResponse } from "next/server";

function unavailable(message: string, status = 503) {
  return NextResponse.json(
    {
      error: {
        code: status === 400 ? "INVALID_REQUEST" : "SHARE_UNAVAILABLE",
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
  if (!apiUrl) {
    return unavailable("This disclosure is temporarily unavailable.");
  }

  const pathname = new URL(request.url).pathname;
  const token = decodeURIComponent(pathname.split("/").filter(Boolean).at(-1) ?? "");
  if (!/^shr_[A-Za-z0-9_-]{40,64}$/.test(token)) {
    return unavailable("This disclosure link is invalid.", 400);
  }

  const upstream = await fetch(
    `${apiUrl}/v1/share/${encodeURIComponent(token)}`,
    { cache: "no-store" },
  );
  const body = await upstream.text();
  return new Response(body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "x-request-id": upstream.headers.get("x-request-id") ?? "",
    },
  });
}
