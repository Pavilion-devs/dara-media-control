import { Navbar } from "@/components/shell/navbar";

/**
 * Public shell for the landing page and Verify. Kept chrome-light on purpose:
 * outsiders land here, and the record is the subject, not the navigation.
 */
export default function PublicLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen bg-page text-ink">
      <Navbar />
      {children}
    </div>
  );
}
