import { NextResponse } from "next/server";

import { getChatGPTUser } from "../../../../chatgpt-auth";

function error(message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code: status === 401 ? "UNAUTHORIZED" : "REGENERATION_UNAVAILABLE",
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
  if (!user) return error("Sign in to regenerate a Dara asset.", 401);

  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (!apiUrl || !token) {
    return error("Live regeneration is not connected.", 503);
  }

  const segments = new URL(request.url).pathname.split("/").filter(Boolean);
  const jobId = decodeURIComponent(segments.at(-2) ?? "");
  if (!/^job_[0-9a-f]{20}$/.test(jobId)) {
    return error("The live job identifier is invalid.", 400);
  }

  const upstream = await fetch(`${apiUrl}/v1/regenerate/${jobId}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Dara-Actor": user.email,
    },
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
