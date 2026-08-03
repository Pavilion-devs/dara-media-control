import { LandingPage } from "@/components/landing/landing-page";

/**
 * Retained alias for the product overview. Several documents link here, so the
 * route keeps serving the same page rather than breaking those references.
 */
export default function AboutPage() {
  return <LandingPage />;
}
