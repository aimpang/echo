import { describe, it, expect } from "vitest";
import { frameIndexAt, type SplatFrame } from "./frames";

const frames: SplatFrame[] = [
  { url: "0", timeSeconds: 0 },
  { url: "1", timeSeconds: 1 },
  { url: "2", timeSeconds: 2 },
  { url: "3", timeSeconds: 3 },
];

describe("frameIndexAt", () => {
  it("returns 0 for an empty list", () => {
    expect(frameIndexAt([], 5)).toBe(0);
  });

  it("clamps time below the first frame to index 0", () => {
    expect(frameIndexAt(frames, -1)).toBe(0);
  });

  it("clamps time after the last frame to the last index", () => {
    expect(frameIndexAt(frames, 999)).toBe(frames.length - 1);
  });

  it("returns the exact frame when the time matches", () => {
    for (let i = 0; i < frames.length; i++) {
      expect(frameIndexAt(frames, frames[i].timeSeconds)).toBe(i);
    }
  });

  it("returns the most recent frame before the given time", () => {
    expect(frameIndexAt(frames, 0.5)).toBe(0);
    expect(frameIndexAt(frames, 1.5)).toBe(1);
    expect(frameIndexAt(frames, 2.999)).toBe(2);
  });

  it("handles non-uniform spacing", () => {
    const sparse: SplatFrame[] = [
      { url: "a", timeSeconds: 0 },
      { url: "b", timeSeconds: 10 },
      { url: "c", timeSeconds: 10.5 },
    ];
    expect(frameIndexAt(sparse, 5)).toBe(0);
    expect(frameIndexAt(sparse, 10)).toBe(1);
    expect(frameIndexAt(sparse, 10.4)).toBe(1);
    expect(frameIndexAt(sparse, 10.5)).toBe(2);
  });
});
