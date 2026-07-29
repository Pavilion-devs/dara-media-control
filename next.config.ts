import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit the self-contained Node server used by the public TierHive judge
  // deployment. Vinext still emits the Cloudflare Worker bundle used by Sites.
  output: "standalone",
};

export default nextConfig;
