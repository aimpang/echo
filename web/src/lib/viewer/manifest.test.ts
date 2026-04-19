import { describe, expect, it } from "vitest";
import {
  MANIFEST_VERSION,
  isManifestPath,
  manifestFromJson,
  parseManifestJson,
  resolveFrameDirectory,
} from "./manifest";

describe("isManifestPath", () => {
  it("matches manifest.json paths", () => {
    expect(isManifestPath("user-1/mem-1/manifest.json")).toBe(true);
    expect(isManifestPath("manifest.json")).toBe(true);
  });
  it("rejects splat paths", () => {
    expect(isManifestPath("user-1/mem-1/frame_00000.splat")).toBe(false);
    expect(isManifestPath("a.splat")).toBe(false);
  });
  it("handles empty/undefined", () => {
    expect(isManifestPath("")).toBe(false);
    expect(isManifestPath(null)).toBe(false);
    expect(isManifestPath(undefined)).toBe(false);
  });
});

describe("resolveFrameDirectory", () => {
  it("strips trailing manifest.json", () => {
    expect(resolveFrameDirectory("user-1/mem-1/manifest.json")).toBe(
      "user-1/mem-1",
    );
  });
  it("returns empty when manifest is at root", () => {
    expect(resolveFrameDirectory("manifest.json")).toBe("");
  });
});

describe("parseManifestJson", () => {
  it("parses a well-formed manifest", () => {
    const raw = JSON.stringify({
      version: MANIFEST_VERSION,
      durationSeconds: 1.5,
      frames: [
        { url: "frame_00000.splat", timeSeconds: 0 },
        { url: "frame_00001.splat", timeSeconds: 0.5 },
        { url: "frame_00002.splat", timeSeconds: 1.5 },
      ],
    });
    const m = parseManifestJson(raw);
    expect(m.frames.length).toBe(3);
    expect(m.frames[1]).toEqual({
      url: "frame_00001.splat",
      timeSeconds: 0.5,
    });
    expect(m.durationSeconds).toBe(1.5);
  });

  it("throws on malformed input", () => {
    expect(() => parseManifestJson("not json")).toThrow();
  });

  it("throws on missing frames", () => {
    expect(() => parseManifestJson(JSON.stringify({ version: 1 }))).toThrow();
  });

  it("throws on unsupported version", () => {
    const raw = JSON.stringify({
      version: 999,
      durationSeconds: 0,
      frames: [],
    });
    expect(() => parseManifestJson(raw)).toThrow(/version/i);
  });
});

describe("manifestFromJson", () => {
  it("normalizes frames sorted by time", () => {
    const m = manifestFromJson({
      version: MANIFEST_VERSION,
      durationSeconds: 2,
      frames: [
        { url: "b.splat", timeSeconds: 1 },
        { url: "a.splat", timeSeconds: 0 },
        { url: "c.splat", timeSeconds: 2 },
      ],
    });
    expect(m.frames.map((f) => f.url)).toEqual([
      "a.splat",
      "b.splat",
      "c.splat",
    ]);
  });

  it("coerces numeric times", () => {
    const m = manifestFromJson({
      version: MANIFEST_VERSION,
      durationSeconds: "1" as unknown as number,
      frames: [
        { url: "a.splat", timeSeconds: "0" as unknown as number },
        { url: "b.splat", timeSeconds: "1" as unknown as number },
      ],
    });
    expect(m.durationSeconds).toBe(1);
    expect(m.frames[1].timeSeconds).toBe(1);
  });
});
