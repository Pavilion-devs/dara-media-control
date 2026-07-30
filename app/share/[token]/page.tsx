import { ShareScreen } from "./share-screen";

export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ShareScreen token={token} />;
}
