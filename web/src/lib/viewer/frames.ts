export type SplatFrame = {
  url: string;
  timeSeconds: number;
};

export function frameIndexAt(frames: SplatFrame[], time: number): number {
  if (frames.length === 0) return 0;
  if (time <= frames[0].timeSeconds) return 0;
  const last = frames.length - 1;
  if (time >= frames[last].timeSeconds) return last;

  let lo = 0;
  let hi = last;
  while (lo < hi - 1) {
    const mid = (lo + hi) >> 1;
    if (frames[mid].timeSeconds <= time) lo = mid;
    else hi = mid;
  }
  return lo;
}
