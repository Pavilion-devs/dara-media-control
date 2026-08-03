export type DocPage = {
  title: string;
  slug: string;
  summary: string;
};

export type DocGroup = {
  title: string;
  items: DocPage[];
};

/** Sidebar structure. Drives the sidebar, ⌘K search, and prev/next footer. */
export const docsNav: DocGroup[] = [
  {
    title: "Getting started",
    items: [
      {
        title: "Overview",
        slug: "/docs",
        summary:
          "What Dara is: a control plane that makes provenance and cost part of the media supply chain.",
      },
      {
        title: "Quickstart",
        slug: "/docs/quickstart",
        summary:
          "Run the API and web app locally, then verify a file without spending anything.",
      },
      {
        title: "Installation & setup",
        slug: "/docs/setup",
        summary:
          "Python, Node, Backblaze B2 credentials, and the environment variables that matter.",
      },
    ],
  },
  {
    title: "Concepts",
    items: [
      {
        title: "How it works",
        slug: "/docs/how-it-works",
        summary:
          "Policy clears the brief, the pipeline runs under watch, and the record outlives the file.",
      },
      {
        title: "Architecture",
        slug: "/docs/architecture",
        summary:
          "Web tier, Python control plane, providers, and one B2 bucket doing every storage job.",
      },
      {
        title: "Trust model",
        slug: "/docs/trust-model",
        summary:
          "What Dara proves, what it does not, and why that boundary is stated rather than hidden.",
      },
    ],
  },
  {
    title: "The four pillars",
    items: [
      {
        title: "Verify",
        slug: "/docs/verify",
        summary:
          "Public file verification with embedded-manifest and content-addressed lookup paths.",
      },
      {
        title: "Govern",
        slug: "/docs/policy",
        summary:
          "Typed policy documents enforced at four points, the first before any provider is called.",
      },
      {
        title: "Generate",
        slug: "/docs/pipelines",
        summary:
          "Still, motion, voice and regeneration pipelines with fallback chains and an agentic QA loop.",
      },
      {
        title: "Account",
        slug: "/docs/ledger",
        summary:
          "Immutable Parquet in B2, queried in place by DuckDB, including work that never shipped.",
      },
    ],
  },
  {
    title: "Reference",
    items: [
      {
        title: "API",
        slug: "/docs/api",
        summary:
          "Public and authenticated endpoints, error envelope, and rate limits.",
      },
      {
        title: "Data model",
        slug: "/docs/data-model",
        summary:
          "Bucket layout, object schemas, ledger tables, identifiers, and how money is represented.",
      },
      {
        title: "Providers & models",
        slug: "/docs/providers",
        summary:
          "Which model serves which step, the fallback routes, and how cost is estimated.",
      },
    ],
  },
];

/** Flat, ordered list used by prev/next and the search palette. */
export const flatDocs: DocPage[] = docsNav.flatMap((group) => group.items);
