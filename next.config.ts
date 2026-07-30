import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit the self-contained Node server used by the public TierHive judge
  // deployment. Vinext still emits the Cloudflare Worker bundle used by Sites.
  output: "standalone",
  experimental: {
    serverActions: {
      // Vinext applies this guard before App Router handlers. Dara streams unknown
      // files to FastAPI, whose own DARA_MAX_UPLOAD_MB limit remains authoritative.
      bodySizeLimit: "100mb",
    },
  },
};

export default nextConfig;
