import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { UploadForm } from "./upload-form";

export default async function NewMemoryPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <main className="min-h-dvh">
      <nav className="flex items-center justify-between px-6 py-5 max-w-6xl mx-auto w-full">
        <Link href="/" className="font-semibold text-lg tracking-tight">
          Echoes
        </Link>
        <Link href="/dashboard" className="btn btn-ghost">
          Cancel
        </Link>
      </nav>
      <section className="px-6 pb-20 max-w-3xl mx-auto">
        <h1 className="text-4xl font-semibold tracking-tight">Create a memory</h1>
        <p className="text-[color:var(--muted)] mt-3">
          Upload a 15–45 second video. We&apos;ll turn it into a 4D scene you
          can walk through.
        </p>
        <div className="mt-8">
          <UploadForm />
        </div>
      </section>
    </main>
  );
}
