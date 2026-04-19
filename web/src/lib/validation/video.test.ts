import { describe, it, expect } from "vitest";
import {
  validateVideoFile,
  VIDEO_MIN_SECONDS,
  VIDEO_MAX_SECONDS,
  VIDEO_MAX_BYTES,
  ACCEPTED_VIDEO_MIME_TYPES,
} from "./video";

const ok = {
  mimeType: "video/mp4",
  sizeBytes: 25_000_000,
  durationSeconds: 30,
};

describe("validateVideoFile", () => {
  it("accepts a valid mp4 within bounds", () => {
    expect(validateVideoFile(ok)).toEqual({ ok: true });
  });

  it("accepts all documented mime types", () => {
    for (const mimeType of ACCEPTED_VIDEO_MIME_TYPES) {
      expect(validateVideoFile({ ...ok, mimeType })).toEqual({ ok: true });
    }
  });

  it("rejects unsupported mime types", () => {
    const result = validateVideoFile({ ...ok, mimeType: "image/png" });
    expect(result).toEqual({
      ok: false,
      code: "unsupported_type",
      message: expect.stringMatching(/video/i),
    });
  });

  it("rejects durations shorter than the minimum", () => {
    const result = validateVideoFile({
      ...ok,
      durationSeconds: VIDEO_MIN_SECONDS - 0.1,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("too_short");
      expect(result.message).toContain(`${VIDEO_MIN_SECONDS}`);
    }
  });

  it("rejects durations longer than the maximum", () => {
    const result = validateVideoFile({
      ...ok,
      durationSeconds: VIDEO_MAX_SECONDS + 0.1,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.code).toBe("too_long");
      expect(result.message).toContain(`${VIDEO_MAX_SECONDS}`);
    }
  });

  it("accepts durations exactly at the boundaries", () => {
    expect(
      validateVideoFile({ ...ok, durationSeconds: VIDEO_MIN_SECONDS }).ok,
    ).toBe(true);
    expect(
      validateVideoFile({ ...ok, durationSeconds: VIDEO_MAX_SECONDS }).ok,
    ).toBe(true);
  });

  it("rejects files exceeding the size cap", () => {
    const result = validateVideoFile({
      ...ok,
      sizeBytes: VIDEO_MAX_BYTES + 1,
    });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("too_large");
  });

  it("rejects zero-byte files", () => {
    const result = validateVideoFile({ ...ok, sizeBytes: 0 });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("empty");
  });

  it("rejects non-finite durations", () => {
    const result = validateVideoFile({ ...ok, durationSeconds: NaN });
    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.code).toBe("invalid_duration");
  });
});
