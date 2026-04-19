"use server";

import { revalidatePath } from "next/cache";
import { createClient } from "@/lib/supabase/server";
import type { MemoryPrivacy } from "@/lib/supabase/database.types";

export async function updatePrivacyAction(
  memoryId: string,
  privacy: MemoryPrivacy,
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Not authenticated" };

  const { error } = await supabase
    .from("memories")
    .update({ privacy })
    .eq("id", memoryId)
    .eq("user_id", user.id);

  if (error) return { ok: false, error: error.message };
  revalidatePath(`/m/${memoryId}`);
  return { ok: true };
}

export async function deleteMemoryAction(
  memoryId: string,
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Not authenticated" };

  const { error } = await supabase
    .from("memories")
    .delete()
    .eq("id", memoryId)
    .eq("user_id", user.id);

  if (error) return { ok: false, error: error.message };
  revalidatePath("/dashboard");
  return { ok: true };
}
