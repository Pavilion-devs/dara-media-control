import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host = requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host") ?? "localhost:3001";
  const protocol = requestHeaders.get("x-forwarded-proto") ?? (host.startsWith("localhost") ? "http" : "https");
  const origin = `${protocol}://${host}`;

  return {
    metadataBase: new URL(origin),
    title: "Dara — Governed media generation",
    description:
      "Governed AI media pipelines, verifiable provenance, and an honest spend ledger.",
    icons: {
      icon: "/favicon.png",
      shortcut: "/favicon.png",
    },
    openGraph: {
      title: "Dara — Make the work. Keep the record.",
      description: "Governed media generation with verifiable provenance and honest cost.",
      images: [{ url: `${origin}/og.png`, width: 1200, height: 630, alt: "Dara — governed media generation" }],
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: "Dara — Make the work. Keep the record.",
      description: "Governed media generation with verifiable provenance and honest cost.",
      images: [`${origin}/og.png`],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
