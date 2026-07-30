import { Sidebar } from "@/components/shell/sidebar";

/** Operator shell: persistent sidebar, dense content column. */
export default function AppLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="min-h-screen bg-page text-ink">
      <Sidebar />
      <div className="lg:pl-64">
        <main className="mx-auto w-full max-w-[1500px] px-4 py-8 md:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}
