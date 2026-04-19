export const MEMORY_STATUSES = [
  "uploading",
  "scanning",
  "processing",
  "ready",
  "upload_failed",
  "rejected",
  "processing_failed",
] as const;

export type MemoryStatus = (typeof MEMORY_STATUSES)[number];

export const TERMINAL_STATUSES: readonly MemoryStatus[] = [
  "ready",
  "upload_failed",
  "rejected",
  "processing_failed",
];

export type MemoryEvent =
  | "upload_completed"
  | "upload_failed"
  | "scan_passed"
  | "scan_rejected"
  | "scan_failed"
  | "processing_completed"
  | "processing_failed";

const ALLOWED_TRANSITIONS: Record<MemoryStatus, readonly MemoryStatus[]> = {
  uploading: ["scanning", "upload_failed"],
  scanning: ["processing", "rejected", "processing_failed"],
  processing: ["ready", "processing_failed"],
  ready: [],
  upload_failed: [],
  rejected: [],
  processing_failed: [],
};

const EVENT_RESULTS: Record<MemoryEvent, MemoryStatus> = {
  upload_completed: "scanning",
  upload_failed: "upload_failed",
  scan_passed: "processing",
  scan_rejected: "rejected",
  scan_failed: "processing_failed",
  processing_completed: "ready",
  processing_failed: "processing_failed",
};

export function isTerminal(status: MemoryStatus): boolean {
  return TERMINAL_STATUSES.includes(status);
}

export function canTransition(from: MemoryStatus, to: MemoryStatus): boolean {
  return ALLOWED_TRANSITIONS[from].includes(to);
}

export function transition(
  current: MemoryStatus,
  event: MemoryEvent,
): MemoryStatus {
  const next = EVENT_RESULTS[event];
  if (!canTransition(current, next)) {
    throw new Error(
      `Invalid transition: cannot apply event "${event}" (→ ${next}) from status "${current}"`,
    );
  }
  return next;
}
