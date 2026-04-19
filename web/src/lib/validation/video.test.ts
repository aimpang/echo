import { describe, it, expect } from "vitest";
import {
  validateVideoFile,
  VIDEO_MIN_SECONDS,
  VIDEO_MAX_SECONDS,
  VIDEO_MAX_BYTES,
  ACCEPTED_VIDEO_MIME_TYPES,
  type VideoValidationResult,
} from "./video";

const ok = {
  mimeType: "video/mp4",
  sizeBytes: 25_000_000,
  durationSeconds: 30,
};

function expectRejection(
  result: VideoValidationResult,
  code: Extract<VideoValidationResult, { ok: false }>["code"],
) {
  expect(result.ok).toBe(false);
  if (!result.ok) expect(result.code).toBe(code);
  return result as Extract<VideoValidationResult, { ok: false }>;
}

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
    const rejection = expectRejection(
      validateVideoFile({ ...ok, durationSeconds: VIDEO_MIN_SECONDS - 0.1 }),
      "too_short",
    );
    expect(rejection.message).toContain(`${VIDEO_MIN_SECONDS}`);
  });

  it("rejects durations longer than the maximum", () => {
    const rejection = expectRejection(
      validateVideoFile({ ...ok, durationSeconds: VIDEO_MAX_SECONDS + 0.1 }),
      "too_long",
    );
    expect(rejection.message).toContain(`${VIDEO_MAX_SECONDS}`);
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
    expectRejection(
      validateVideoFile({ ...ok, sizeBytes: VIDEO_MAX_BYTES + 1 }),
      "too_large",
    );
  });

  it("rejects zero-byte files", () => {
    expectRejection(
      validateVideoFile({ ...ok, sizeBytes: 0 }),
      "empty",
    );
  });

  it("rejects non-finite durations", () => {
    expectRejection(
      validateVideoFile({ ...ok, durationSeconds: NaN }),
      "invalid_duration",
    );
  });
});
