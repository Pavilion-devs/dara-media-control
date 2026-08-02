import type { Metadata } from "next";

import { AssetsScreen } from "./assets-screen";

export const metadata: Metadata = {
  title: "Assets — Dara",
  description: "Live published assets and their B2-backed provenance records.",
};

export default function AssetsPage() {
  return <AssetsScreen />;
}
