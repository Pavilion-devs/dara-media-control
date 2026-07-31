import { NextResponse } from "next/server";

import { anonymousActor } from "../../../anonymous-actor";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 400 ? "INVALID_PROJECT" : "PROJECTS_UNAVAILABLE",
        message,
        details: {},
        request_id: null,
      },
    },
    { status },
  );
}

async function proxy(request: Request, method: "GET" | "PUT") {
  const projectId = decodeURIComponent(
    new URL(request.url).pathname.split("/").filter(Boolean).at(-1) ?? "",
  );
  if (!/^prj_[A-Za-z0-9_-]{2,80}$/.test(projectId)) {
    return error("The project identifier is invalid.", 400);
  }
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) return error("Project records are not connected.", 503);
  const upstream = await fetch(
    `${apiUrl}/v1/projects/${encodeURIComponent(projectId)}`,
    {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(method === "PUT" ? { "X-Dara-Actor": await anonymousActor(request) } : {}),
        ...(method === "PUT" ? { "Content-Type": "application/json" } : {}),
      },
      body: method === "PUT" ? await request.text() : undefined,
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

export async function GET(request: Request) {
  return proxy(request, "GET");
}

export async function PUT(request: Request) {
  return proxy(request, "PUT");
}
