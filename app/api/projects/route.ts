import { NextResponse } from "next/server";

import { anonymousActor } from "../../anonymous-actor";

function unavailable() {
  return NextResponse.json(
    {
      error: {
        code: "PROJECTS_UNAVAILABLE",
        message: "Project records are not connected on this deployment.",
        details: {},
        request_id: null,
      },
    },
    { status: 503 },
  );
}

async function proxy(request: Request, method: "GET" | "POST") {
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) return unavailable();
  const upstream = await fetch(`${apiUrl}/v1/projects`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(method === "POST" ? { "X-Dara-Actor": await anonymousActor(request) } : {}),
      ...(method === "POST" ? { "Content-Type": "application/json" } : {}),
    },
    body: method === "POST" ? await request.text() : undefined,
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

export async function GET(request: Request) {
  return proxy(request, "GET");
}

export async function POST(request: Request) {
  return proxy(request, "POST");
}
