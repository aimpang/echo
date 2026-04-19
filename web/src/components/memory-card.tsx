import Link from "next/link";
import type { MemoryRow } from "@/lib/supabase/database.types";
import { StatusBadge } from "./status-badge";

export function MemoryCard({ memory }: { memory: MemoryRow }) {
  const href =
    memory.status === "ready" ? `/m/${memory.id}` : `/m/${memory.id}`;

  return (
    <Link
      href={href}
      className="card p-5 hover:border-[color:var(--accent)] transition-colors"
    >
      <div className="aspect-video rounded-lg bg-[color:var(--surface-2)] mb-4 overflow-hidden flex items-center justify-center">
        <span className="text-[color:var(--muted)] text-xs">
          {memory.status === "ready" ? "Preview" : "Processing…"}
        </span>
      </div>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-semibold truncate">{memory.title}</h3>
          <p className="text-xs text-[color:var(--muted)] mt-1">
            {new Date(memory.created_at).toLocaleDateString()}
          </p>
        </div>
        <StatusBadge status={memory.status} />
      </div>
    </Link>
  );
}
