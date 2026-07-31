const textEncoder = new TextEncoder();

function firstForwardedValue(value: string | null): string | null {
  const candidate = value?.split(",", 1)[0]?.trim();
  return candidate || null;
}

export function clientAddress(request: Request): string {
  const trustedProxy =
    process.env.DARA_TRUSTED_PROXY ??
    (process.env.VERCEL === "1" ? "vercel" : "cloudflare");
  if (trustedProxy === "vercel") {
    return (
      firstForwardedValue(request.headers.get("x-vercel-forwarded-for")) ??
      firstForwardedValue(request.headers.get("x-real-ip")) ??
      "unknown"
    );
  }
  if (trustedProxy === "cloudflare") {
    return firstForwardedValue(request.headers.get("cf-connecting-ip")) ?? "unknown";
  }
  return (
    firstForwardedValue(request.headers.get("x-forwarded-for")) ??
    firstForwardedValue(request.headers.get("x-real-ip")) ??
    "unknown"
  );
}

/**
 * Produce a stable, non-reversible actor identifier for abuse controls and audit
 * records without forwarding a visitor's email address or raw IP address.
 */
export async function anonymousActor(request: Request): Promise<string> {
  const secret =
    process.env.DARA_ANON_ACTOR_SECRET ??
    process.env.DARA_API_TOKEN ??
    "dara-local-development";
  const key = await crypto.subtle.importKey(
    "raw",
    textEncoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    textEncoder.encode(clientAddress(request)),
  );
  const digest = Array.from(new Uint8Array(signature), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
  return `anon_${digest.slice(0, 32)}`;
}
