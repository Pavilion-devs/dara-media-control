import { NextResponse } from "next/server";

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

  const formData = await request.formData();
  const upstream = await fetch(`${apiUrl}/v1/verify`, {
    method: "POST",
    body: formData,
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
