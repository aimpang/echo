"use client";

import { useCallback, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  validateVideoFile,
  ACCEPTED_VIDEO_MIME_TYPES,
  type VideoValidationResult,
} from "@/lib/validation/video";
import { readVideoMetadata } from "@/lib/validation/read-video-metadata";
import {
  createMemoryAction,
  markUploadCompletedAction,
  markUploadFailedAction,
} from "./actions";

type Phase =
  | { kind: "idle" }
  | { kind: "reading"; file: File }
  | { kind: "ready"; file: File; durationSeconds: number }
  | { kind: "uploading"; progress: number }
  | { kind: "finalizing" }
  | { kind: "error"; message: string };

export function UploadForm() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [capturedAt, setCapturedAt] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  const handleFile = useCallback(async (file: File) => {
    setPhase({ kind: "reading", file });
    try {
      const meta = await readVideoMetadata(file);
      const result: VideoValidationResult = validateVideoFile({
        mimeType: file.type,
        sizeBytes: file.size,
        durationSeconds: meta.durationSeconds,
      });
      if (!result.ok) {
        setPhase({ kind: "error", message: result.message });
        return;
      }
      setPhase({
        kind: "ready",
        file,
        durationSeconds: meta.durationSeconds,
      });
      if (!title) setTitle(file.name.replace(/\.[^.]+$/, ""));
    } catch {
      setPhase({
        kind: "error",
        message: "Could not read that video. Try a different file.",
      });
    }
  }, [title]);

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (phase.kind !== "ready") return;

    const file = phase.file;
    const durationSeconds = phase.durationSeconds;

    const created = await createMemoryAction({
      title,
      description: description || undefined,
      capturedAt: capturedAt || null,
      durationSeconds,
      sizeBytes: file.size,
      mimeType: file.type,
    });

    if (!created.ok) {
      setPhase({ kind: "error", message: created.error });
      return;
    }

    setPhase({ kind: "uploading", progress: 0 });

    const supabase = createClient();
    const { error: uploadError } = await supabase.storage
      .from("videos")
      .upload(created.uploadPath, file, {
        cacheControl: "3600",
        upsert: false,
        contentType: file.type,
      });

    if (uploadError) {
      await markUploadFailedAction(created.id);
      setPhase({ kind: "error", message: uploadError.message });
      return;
    }

    setPhase({ kind: "finalizing" });
    const finalized = await markUploadCompletedAction(created.id);
    if (!finalized.ok) {
      setPhase({
        kind: "error",
        message: finalized.error ?? "Could not finalize upload",
      });
      return;
    }

    router.push(`/m/${created.id}`);
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-6">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`card cursor-pointer p-10 text-center transition-colors ${
          isDragging
            ? "border-[color:var(--accent)] bg-[color:var(--surface-2)]"
            : "hover:border-[color:var(--accent)]"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_VIDEO_MIME_TYPES.join(",")}
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
        {phase.kind === "idle" && (
          <>
            <p className="text-lg font-semibold">Drop a video here</p>
            <p className="text-sm text-[color:var(--muted)] mt-1">
              or click to browse. MP4, MOV, or WebM. 15–45 seconds.
            </p>
          </>
        )}
        {phase.kind === "reading" && (
          <p className="text-sm text-[color:var(--muted)]">
            Reading {phase.file.name}…
          </p>
        )}
        {phase.kind === "ready" && (
          <>
            <p className="font-semibold">{phase.file.name}</p>
            <p className="text-sm text-[color:var(--muted)] mt-1">
              {phase.durationSeconds.toFixed(1)}s ·{" "}
              {(phase.file.size / (1024 * 1024)).toFixed(1)} MB
            </p>
          </>
        )}
        {phase.kind === "uploading" && (
          <>
            <p className="font-semibold">Uploading…</p>
            <div className="mt-4 h-2 rounded-full bg-[color:var(--surface-2)] overflow-hidden">
              <div
                className="h-full bg-[color:var(--accent)] transition-all"
                style={{ width: `${phase.progress}%` }}
              />
            </div>
          </>
        )}
        {phase.kind === "finalizing" && (
          <p className="text-sm text-[color:var(--muted)]">Finishing up…</p>
        )}
        {phase.kind === "error" && (
          <p className="text-sm text-[color:var(--danger)]">{phase.message}</p>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="flex flex-col gap-2">
          <label className="text-sm text-[color:var(--muted)]" htmlFor="title">
            Title
          </label>
          <input
            id="title"
            className="input"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="A summer afternoon"
            required
            maxLength={120}
          />
        </div>
        <div className="flex flex-col gap-2">
          <label
            className="text-sm text-[color:var(--muted)]"
            htmlFor="capturedAt"
          >
            When was this?
          </label>
          <input
            id="capturedAt"
            type="date"
            className="input"
            value={capturedAt}
            onChange={(e) => setCapturedAt(e.target.value)}
          />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label
          className="text-sm text-[color:var(--muted)]"
          htmlFor="description"
        >
          Description (optional)
        </label>
        <textarea
          id="description"
          className="input resize-none"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          maxLength={2000}
          placeholder="What&apos;s happening in this memory?"
        />
      </div>

      <div className="card p-4 text-sm text-[color:var(--muted)] space-y-3">
        <div>
          <p className="font-semibold text-[color:var(--foreground)] mb-1">
            Private by default
          </p>
          <p>
            Your video is uploaded privately to your account. Only you can see
            it unless you create a share link.
          </p>
        </div>
        <div>
          <p className="font-semibold text-[color:var(--foreground)] mb-1">
            Safety review
          </p>
          <p>
            During early access, uploads are auto-approved and spot-checked
            manually. Automated moderation is coming soon — please only upload
            content you have the right to share.
          </p>
        </div>
      </div>

      <button
        type="submit"
        disabled={
          phase.kind !== "ready" || title.trim().length === 0
        }
        className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
      >
        Create memory
      </button>
    </form>
  );
}
