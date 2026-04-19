import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import type { MemoryRow } from "@/lib/supabase/database.types";
import { StatusBadge } from "@/components/status-badge";
import { SplatViewer } from "@/components/splat-viewer";
import { loadSplatSource } from "@/lib/viewer/load-manifest";
import { SharePanel } from "./share-panel";

type PageParams = { id: string };

export default async function MemoryPage({
  params,
}: {
  params: Promise<PageParams>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data } = await supabase
    .from("memories")
    .select("*")
    .eq("id", id)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!data) notFound();
  const memory = data as MemoryRow;

  const splatSource =
    memory.status === "ready"
      ? await loadSplatSource(supabase, memory.splat_path)
      : null;

  return (
    <main className="min-h-dvh">
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <Link href="/dashboard" className="font-semibold text-lg tracking-tight">
          ← Echoes
        </Link>
        <StatusBadge status={memory.status} />
      </nav>

      <section className="px-6 pb-16 max-w-6xl mx-auto">
        <h1 className="text-3xl font-semibold tracking-tight">
          {memory.title}
        </h1>
        {memory.description && (
          <p className="text-[color:var(--muted)] mt-2">{memory.description}</p>
        )}

        <div className="mt-8 aspect-video card p-0 overflow-hidden">
          {splatSource?.kind === "frames" ? (
            <SplatViewer frames={splatSource.frames} initialPlaying />
          ) : splatSource?.kind === "single" ? (
            <SplatViewer src={splatSource.url} />
          ) : (
            <ProcessingPlaceholder status={memory.status} />
          )}
        </div>

        <div className="mt-8 grid md:grid-cols-2 gap-4">
          <div className="card p-5">
            <h3 className="font-semibold">Details</h3>
            <dl className="mt-3 space-y-2 text-sm">
              <Detail label="Duration">
                {memory.duration_seconds?.toFixed(1) ?? "—"}s
              </Detail>
              <Detail label="Captured">
                {memory.captured_at
                  ? new Date(memory.captured_at).toLocaleDateString()
                  : "—"}
              </Detail>
              <Detail label="Uploaded">
                {new Date(memory.created_at).toLocaleString()}
              </Detail>
            </dl>
          </div>
          <SharePanel memory={memory} />
        </div>
      </section>
    </main>
  );
}

function Detail({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex justify-between">
      <dt className="text-[color:var(--muted)]">{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

function ProcessingPlaceholder({ status }: { status: MemoryRow["status"] }) {
  const messages: Record<MemoryRow["status"], string> = {
    uploading: "Uploading your video…",
    scanning: "Running safety checks…",
    processing:
      "Turning your video into a 4D scene. This can take a few minutes.",
    ready: "Ready.",
    upload_failed: "Upload failed. Try again.",
    rejected: "This video couldn't be processed.",
    processing_failed: "Processing failed. Try re-uploading.",
  };
  return (
    <div className="w-full h-full flex items-center justify-center text-center p-10">
      <p className="text-[color:var(--muted)] max-w-md">{messages[status]}</p>
    </div>
  );
}
