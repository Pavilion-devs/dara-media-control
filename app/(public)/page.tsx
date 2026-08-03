import { LandingPage } from "@/components/landing/landing-page";

/**
 * The landing page is served at the root. It renders a normal 200 rather than a
 * 3xx, so infrastructure health checks probing `/` still see a healthy backend —
 * the property the previous meta-refresh pass-through existed to preserve.
 */
export default function HomePage() {
  return <LandingPage />;
}
