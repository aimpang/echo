import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { MemoryRow } from "@/lib/supabase/database.types";
import { MemoryCard } from "@/components/memory-card";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: memories } = await supabase
    .from("memories")
    .select("*")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  const list = (memories ?? []) as MemoryRow[];

  return (
    <main className="min-h-dvh">
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <Link href="/" className="font-semibold text-lg tracking-tight">
          Echoes
        </Link>
        <div className="flex gap-3 items-center">
          <span className="text-sm text-[color:var(--muted)]">
            {user.email}
          </span>
          <Link href="/new" className="btn btn-primary">
            New memory
          </Link>
          <form action="/auth/signout" method="post">
            <button className="btn btn-ghost" type="submit">
              Sign out
            </button>
          </form>
        </div>
      </nav>

      <section className="px-6 pb-16 max-w-6xl mx-auto">
        <div className="flex items-baseline justify-between mb-6">
          <h1 className="text-3xl font-semibold tracking-tight">
            Your memories
          </h1>
          <p className="text-sm text-[color:var(--muted)]">
            {list.length} {list.length === 1 ? "memory" : "memories"}
          </p>
        </div>

        {list.length === 0 ? (
          <div className="card p-10 text-center">
            <p className="text-lg">No memories yet.</p>
            <p className="text-sm text-[color:var(--muted)] mt-2">
              Upload a short video to get started.
            </p>
            <Link href="/new" className="btn btn-primary mt-6 inline-flex">
              Create your first memory
            </Link>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {list.map((m) => (
              <MemoryCard key={m.id} memory={m} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
