"use server";

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import { generateShareToken } from "@/lib/sharing/token";
import { transition } from "@/lib/memory/status";
import type {
  MemoryInsert,
  MemoryRow,
} from "@/lib/supabase/database.types";

export type CreateMemoryInput = {
  title: string;
  description?: string;
  capturedAt?: string | null;
  durationSeconds: number;
  sizeBytes: number;
  mimeType: string;
};

export type CreateMemoryResult =
  | { ok: true; id: string; uploadPath: string }
  | { ok: false; error: string };

const MIME_EXT: Record<string, string> = {
  "video/mp4": "mp4",
  "video/quicktime": "mov",
  "video/webm": "webm",
};

export async function createMemoryAction(
  input: CreateMemoryInput,
): Promise<CreateMemoryResult> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return { ok: false, error: "Not authenticated" };

  const title = input.title.trim().slice(0, 120);
  if (!title) return { ok: false, error: "Title is required" };

  const ext = MIME_EXT[input.mimeType];
  if (!ext) return { ok: false, error: "Unsupported file type" };

  const id = crypto.randomUUID();
  const uploadPath = `${user.id}/${id}.${ext}`;

  const row: MemoryInsert = {
    id,
    user_id: user.id,
    title,
    description: input.description?.trim() || null,
    captured_at: input.capturedAt ?? null,
    status: "uploading",
    privacy: "private",
    share_token: generateShareToken(),
    source_video_path: uploadPath,
    splat_path: null,
    thumbnail_path: null,
    duration_seconds: input.durationSeconds,
    size_bytes: input.sizeBytes,
    safety_flag: null,
    safety_checked_at: null,
    processing_started_at: null,
    processing_completed_at: null,
  };

  const { error } = await supabase.from("memories").insert(row);
  if (error) return { ok: false, error: error.message };

  return { ok: true, id, uploadPath };
}

export async function markUploadCompletedAction(memoryId: string): Promise<{
  ok: boolean;
  error?: string;
}> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Not authenticated" };

  const { data: existing, error: fetchError } = await supabase
    .from("memories")
    .select("status")
    .eq("id", memoryId)
    .eq("user_id", user.id)
    .single();

  if (fetchError || !existing)
    return { ok: false, error: fetchError?.message ?? "Not found" };

  let nextStatus: MemoryRow["status"];
  try {
    nextStatus = transition(existing.status, "upload_completed");
  } catch (e) {
    return {
      ok: false,
      error: e instanceof Error ? e.message : "Invalid transition",
    };
  }

  const { error } = await supabase
    .from("memories")
    .update({ status: nextStatus })
    .eq("id", memoryId)
    .eq("user_id", user.id);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function markUploadFailedAction(memoryId: string): Promise<void> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return;

  await supabase
    .from("memories")
    .update({ status: "upload_failed" })
    .eq("id", memoryId)
    .eq("user_id", user.id);
}

export async function redirectToMemory(memoryId: string): Promise<never> {
  redirect(`/m/${memoryId}`);
}
