import Link from "next/link";

export default function HomePage() {
  return (
    <main className="min-h-dvh">
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <Link href="/" className="font-semibold text-lg tracking-tight">
          Echoes
        </Link>
        <div className="flex gap-3">
          <Link href="/login" className="btn btn-ghost">
            Sign in
          </Link>
        </div>
      </nav>

      <section className="px-6 pt-16 pb-24 max-w-4xl mx-auto text-center">
        <p className="text-sm uppercase tracking-[0.2em] text-[color:var(--muted)] mb-6">
          4D personal memory vault
        </p>
        <h1 className="text-5xl md:text-7xl font-semibold tracking-tight leading-[1.05]">
          Walk inside your memories.
        </h1>
        <p className="text-lg md:text-xl text-[color:var(--muted)] mt-6 max-w-2xl mx-auto">
          Upload a 15–45 second video. We turn it into a 4D scene you can move
          through, rewind, and share — privately.
        </p>
        <div className="mt-10 flex items-center justify-center gap-3">
          <Link href="/new" className="btn btn-primary text-base">
            Create a memory
          </Link>
          <Link href="/login" className="btn btn-ghost">
            Sign in
          </Link>
        </div>
      </section>

      <section className="px-6 pb-24 max-w-5xl mx-auto grid md:grid-cols-3 gap-4">
        <FeatureCard
          title="Private by default"
          body="Your memories stay yours. Share only when you choose."
        />
        <FeatureCard
          title="Move through time"
          body="Scrub, rewind, and explore scenes from any angle."
        />
        <FeatureCard
          title="Built for home movies"
          body="Short clips are the sweet spot. Tested on an RTX 5080 locally."
        />
      </section>

      <footer className="px-6 py-10 max-w-6xl mx-auto text-sm text-[color:var(--muted)]">
        © {new Date().getFullYear()} Echoes — early access
      </footer>
    </main>
  );
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="card p-6">
      <h3 className="font-semibold text-lg">{title}</h3>
      <p className="text-sm text-[color:var(--muted)] mt-2">{body}</p>
    </div>
  );
}
