import createMDX from "@next/mdx";
import type { NextConfig } from "next";
import rehypeSlug from "rehype-slug";
import remarkGfm from "remark-gfm";

import remarkCodeMeta from "./lib/remark-code-meta.mjs";

const nextConfig: NextConfig = {
  // Emit the self-contained Node server used by the public TierHive judge
  // deployment. Vinext still emits the Cloudflare Worker bundle used by Sites.
  output: "standalone",
  // Documentation pages are authored as MDX under app/docs/**.
  pageExtensions: ["ts", "tsx", "js", "jsx", "md", "mdx"],
  experimental: {
    serverActions: {
      // Vinext applies this guard before App Router handlers. Dara streams unknown
      // files to FastAPI, whose own DARA_MAX_UPLOAD_MB limit remains authoritative.
      bodySizeLimit: "100mb",
    },
  },
};

/**
 * Vinext reads MDX settings by probing the webpack rules that `@next/mdx`
 * installs, then serves them with the Vite-native `@mdx-js/rollup` instead. So
 * the wrapper below is the supported way to get remark/rehype plugins through —
 * no webpack ever runs.
 */
const withMDX = createMDX({
  options: {
    remarkPlugins: [remarkGfm, remarkCodeMeta],
    // Gives every heading an id, which is what the "On this page" rail reads.
    rehypePlugins: [rehypeSlug],
  },
});

export default withMDX(nextConfig);
