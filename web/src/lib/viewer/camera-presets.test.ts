import { describe, it, expect } from "vitest";
import {
  CAMERA_PRESETS,
  cameraPresetByKey,
  isCameraPresetKey,
} from "./camera-presets";

describe("CAMERA_PRESETS", () => {
  it("defines front, side, top, and iso presets", () => {
    const keys = CAMERA_PRESETS.map((p) => p.key);
    expect(keys).toEqual(
      expect.arrayContaining(["front", "side", "top", "iso"]),
    );
  });

  it("every preset has a 3-tuple position and a label", () => {
    for (const preset of CAMERA_PRESETS) {
      expect(preset.position).toHaveLength(3);
      preset.position.forEach((n) => expect(Number.isFinite(n)).toBe(true));
      expect(preset.label.length).toBeGreaterThan(0);
    }
  });

  it("the top preset looks straight down", () => {
    const top = cameraPresetByKey("top");
    const [, y] = top.position;
    expect(y).toBeGreaterThan(0);
  });
});

describe("cameraPresetByKey", () => {
  it("returns the matching preset", () => {
    expect(cameraPresetByKey("front").key).toBe("front");
  });

  it("throws on unknown keys", () => {
    expect(() =>
      cameraPresetByKey("sideways" as unknown as "front"),
    ).toThrow();
  });
});

describe("isCameraPresetKey", () => {
  it("accepts known keys and rejects others", () => {
    expect(isCameraPresetKey("front")).toBe(true);
    expect(isCameraPresetKey("top")).toBe(true);
    expect(isCameraPresetKey("elsewhere")).toBe(false);
    expect(isCameraPresetKey("")).toBe(false);
  });
});
