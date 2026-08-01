/**
 * The zero-spend Studio replay is Dara's judge entry point. The full product
 * story remains available at /about without putting a marketing step in front
 * of the working control plane. This route deliberately returns 200 before the
 * browser moves to /studio so infrastructure health checks do not treat the
 * intended redirect as an unavailable backend.
 */
export default function HomePage() {
  return (
    <main className="flex min-h-[70vh] items-center justify-center px-6 text-center">
      <meta httpEquiv="refresh" content="0;url=/studio" />
      <div>
        <p className="text-sm font-semibold uppercase tracking-widest text-subtle">
          Dara
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          Opening Studio…
        </h1>
        <p className="mt-4 text-muted">
          <a className="text-accent-ink underline" href="/studio">
            Continue to the governed media control plane
          </a>
        </p>
      </div>
    </main>
  );
}
