import Link from "next/link";
import { notFound } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { isValidShareToken } from "@/lib/sharing/token";
import type { MemoryRow } from "@/lib/supabase/database.types";
import { SplatViewer } from "@/components/splat-viewer";

type PageParams = { token: string };

export default async function SharedMemoryPage({
  params,
}: {
  params: Promise<PageParams>;
}) {
  const { token } = await params;
  if (!isValidShareToken(token)) notFound();

  const supabase = await createClient();
  const { data } = await supabase
    .from("memories")
    .select("*")
    .eq("share_token", token)
    .eq("privacy", "link")
    .eq("status", "ready")
    .maybeSingle();

  if (!data) notFound();
  const memory = data as MemoryRow;

  let splatUrl: string | null = null;
  if (memory.splat_path) {
    const { data: signed } = await supabase.storage
      .from("splats")
      .createSignedUrl(memory.splat_path, 60 * 60);
    splatUrl = signed?.signedUrl ?? null;
  }

  return (
    <main className="min-h-dvh">
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <Link href="/" className="font-semibold text-lg tracking-tight">
          Echoes
        </Link>
        <Link href="/login" className="btn btn-ghost text-sm">
          Make your own
        </Link>
      </nav>
      <section className="px-6 pb-16 max-w-5xl mx-auto">
        <h1 className="text-3xl font-semibold tracking-tight">
          {memory.title}
        </h1>
        {memory.description && (
          <p className="text-[color:var(--muted)] mt-2">{memory.description}</p>
        )}
        <div className="mt-6 aspect-video card p-0 overflow-hidden">
          {splatUrl ? (
            <SplatViewer src={splatUrl} />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-[color:var(--muted)]">
              This memory isn&apos;t ready yet.
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
