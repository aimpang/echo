export function formatTimecode(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) {
    return "0:00.0";
  }
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds - minutes * 60;
  const tenths = Math.floor(remainder * 10) / 10;
  const whole = Math.floor(tenths);
  const fraction = Math.round((tenths - whole) * 10);
  return `${minutes}:${String(whole).padStart(2, "0")}.${fraction}`;
}
