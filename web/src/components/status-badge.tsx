import type { MemoryStatus } from "@/lib/memory/status";

const LABELS: Record<MemoryStatus, string> = {
  uploading: "Uploading",
  scanning: "Checking",
  processing: "Processing",
  ready: "Ready",
  upload_failed: "Upload failed",
  rejected: "Not accepted",
  processing_failed: "Processing failed",
};

const COLORS: Record<MemoryStatus, string> = {
  uploading: "bg-sky-900/40 text-sky-300 border-sky-800",
  scanning: "bg-amber-900/40 text-amber-300 border-amber-800",
  processing: "bg-violet-900/40 text-violet-300 border-violet-800",
  ready: "bg-emerald-900/40 text-emerald-300 border-emerald-800",
  upload_failed: "bg-red-900/40 text-red-300 border-red-800",
  rejected: "bg-red-900/40 text-red-300 border-red-800",
  processing_failed: "bg-red-900/40 text-red-300 border-red-800",
};

export function StatusBadge({ status }: { status: MemoryStatus }) {
  return (
    <span
      className={`text-[10px] uppercase tracking-wider font-semibold px-2 py-1 rounded-md border ${COLORS[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
