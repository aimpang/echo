const DEFAULT_FALLBACK = "/dashboard";

export function safeNextPath(
  next: string | null | undefined,
  fallback: string = DEFAULT_FALLBACK,
): string {
  if (!next) return fallback;
  if (!next.startsWith("/")) return fallback;
  if (next.startsWith("//")) return fallback;
  if (next.startsWith("/\\")) return fallback;
  return next;
}
