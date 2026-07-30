import { AssetScreen } from "./asset-screen";

export default async function AssetPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <AssetScreen id={id} />;
}
