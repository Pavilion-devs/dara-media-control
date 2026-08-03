import type { Metadata } from "next";

import { DocsSidebar } from "@/components/docs/docs-sidebar";
import { DocsTopbar } from "@/components/docs/docs-topbar";
import { PrevNext } from "@/components/docs/prev-next";
import { Toc } from "@/components/docs/toc";

export const metadata: Metadata = {
  title: { default: "Dara Docs", template: "%s · Dara Docs" },
  description:
    "Documentation for Dara — governed AI media pipelines, verifiable provenance, and an honest spend ledger.",
};

/**
 * Three-column documentation shell: nav on the left, article in the middle,
 * "On this page" on the right. Theming comes from the root layout, so there is
 * no second theme system here.
 */
export default function DocsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-page text-ink">
      <DocsTopbar />
      <div className="mx-auto flex w-full max-w-[1600px]">
        <DocsSidebar />
        <main className="min-w-0 flex-1 px-6 py-10 lg:px-12">
          {/*
            Full-bleed grid: prose sits in the centre column at a readable
            measure, while a figure can opt into spanning the whole width with
            `col-start-1 col-end-4`. Without this a wide diagram is trapped in
            the 48rem prose column and can only scroll sideways.
          */}
          <article
            className="mx-auto grid w-full max-w-[1120px] grid-cols-[minmax(0,1fr)_min(100%,48rem)_minmax(0,1fr)] [&>*]:col-start-2"
            id="doc-article"
          >
            {children}
            <PrevNext />
          </article>
        </main>
        <Toc />
      </div>
    </div>
  );
}
