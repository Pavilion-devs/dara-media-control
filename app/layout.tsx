import type { Metadata } from "next";
import { headers } from "next/headers";
import { Manrope, Space_Mono } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-manrope",
  display: "swap",
});

const spaceMono = Space_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-space-mono",
  display: "swap",
});

// Resolve the stored theme before first paint so the toggle never flashes the
// wrong surface. Inlined because it must run ahead of hydration.
const themeScript = `(()=>{try{const t=localStorage.getItem("dara-theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch{}})()`;

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
    // The theme script sets data-theme before hydration by design, so React
    // must not try to reconcile that attribute away.
    <html
      className={`${manrope.variable} ${spaceMono.variable}`}
      lang="en"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
