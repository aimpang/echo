export const VIDEO_MIN_SECONDS = 15;
export const VIDEO_MAX_SECONDS = 45;
export const VIDEO_MAX_BYTES = 500 * 1024 * 1024;

export const ACCEPTED_VIDEO_MIME_TYPES = [
  "video/mp4",
  "video/quicktime",
  "video/webm",
] as const;

export type AcceptedVideoMimeType = (typeof ACCEPTED_VIDEO_MIME_TYPES)[number];

export type VideoValidationInput = {
  mimeType: string;
  sizeBytes: number;
  durationSeconds: number;
};

export type VideoValidationError =
  | "unsupported_type"
  | "too_short"
  | "too_long"
  | "too_large"
  | "empty"
  | "invalid_duration";

export type VideoValidationResult =
  | { ok: true }
  | { ok: false; code: VideoValidationError; message: string };

export function validateVideoFile(
  input: VideoValidationInput,
): VideoValidationResult {
  const { mimeType, sizeBytes, durationSeconds } = input;

  if (!ACCEPTED_VIDEO_MIME_TYPES.includes(mimeType as AcceptedVideoMimeType)) {
    return {
      ok: false,
      code: "unsupported_type",
      message: `Unsupported file type. Please upload a video (${ACCEPTED_VIDEO_MIME_TYPES.join(", ")}).`,
    };
  }

  if (sizeBytes <= 0) {
    return { ok: false, code: "empty", message: "File appears to be empty." };
  }

  if (sizeBytes > VIDEO_MAX_BYTES) {
    const maxMb = Math.round(VIDEO_MAX_BYTES / (1024 * 1024));
    return {
      ok: false,
      code: "too_large",
      message: `File is too large. Maximum size is ${maxMb} MB.`,
    };
  }

  if (!Number.isFinite(durationSeconds)) {
    return {
      ok: false,
      code: "invalid_duration",
      message: "Could not determine video duration.",
    };
  }

  if (durationSeconds < VIDEO_MIN_SECONDS) {
    return {
      ok: false,
      code: "too_short",
      message: `Video is too short. Minimum is ${VIDEO_MIN_SECONDS} seconds.`,
    };
  }

  if (durationSeconds > VIDEO_MAX_SECONDS) {
    return {
      ok: false,
      code: "too_long",
      message: `Video is too long. Maximum is ${VIDEO_MAX_SECONDS} seconds.`,
    };
  }

  return { ok: true };
}
