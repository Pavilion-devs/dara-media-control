import { notFound } from "next/navigation";

import { assetRecordSchema, type AssetRecord } from "../../../asset-schema";
import { AssetScreen } from "./asset-screen";

export default async function AssetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let record: AssetRecord | null = null;
  const apiUrl = process.env.DARA_API_URL?.replace(/\/$/, "");
  const token = process.env.DARA_API_TOKEN;
  if (apiUrl && token) {
    const response = await fetch(
      `${apiUrl}/v1/assets/${encodeURIComponent(id)}`,
      { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
    );
    if (response.ok) record = assetRecordSchema.parse(await response.json());
  }
  if (record === null) notFound();
  return <AssetScreen id={id} record={record} />;
}
