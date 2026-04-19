import type { SupabaseClient } from "@supabase/supabase-js";
import type { SplatFrame } from "./frames";
import {
  isManifestPath,
  parseManifestJson,
  resolveFrameDirectory,
} from "./manifest";

const SIGNED_URL_TTL_SECONDS = 60 * 60;

export type LoadedSplatSource =
  | { kind: "single"; url: string }
  | { kind: "frames"; frames: SplatFrame[]; durationSeconds: number }
  | null;

export async function loadSplatSource(
  supabase: SupabaseClient,
  storagePath: string | null | undefined,
): Promise<LoadedSplatSource> {
  if (!storagePath) return null;

  if (!isManifestPath(storagePath)) {
    const { data } = await supabase.storage
      .from("splats")
      .createSignedUrl(storagePath, SIGNED_URL_TTL_SECONDS);
    return data?.signedUrl ? { kind: "single", url: data.signedUrl } : null;
  }

  const { data: blob, error } = await supabase.storage
    .from("splats")
    .download(storagePath);
  if (error || !blob) return null;

  const manifest = parseManifestJson(await blob.text());
  const dir = resolveFrameDirectory(storagePath);

  const framePaths = manifest.frames.map((f) =>
    dir ? `${dir}/${f.url}` : f.url,
  );

  const { data: signed } = await supabase.storage
    .from("splats")
    .createSignedUrls(framePaths, SIGNED_URL_TTL_SECONDS);
  if (!signed) return null;

  const frames: SplatFrame[] = manifest.frames.map((f, i) => ({
    url: signed[i]?.signedUrl ?? "",
    timeSeconds: f.timeSeconds,
  }));

  if (frames.some((f) => !f.url)) return null;

  return {
    kind: "frames",
    frames,
    durationSeconds: manifest.durationSeconds,
  };
}
