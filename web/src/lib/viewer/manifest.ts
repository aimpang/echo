import type { SplatFrame } from "./frames";

export const MANIFEST_VERSION = 1;
export const MANIFEST_FILENAME = "manifest.json";

export type FourDManifest = {
  version: number;
  durationSeconds: number;
  frames: SplatFrame[];
};

export function isManifestPath(path: string | null | undefined): boolean {
  if (!path) return false;
  return path === MANIFEST_FILENAME || path.endsWith(`/${MANIFEST_FILENAME}`);
}

export function resolveFrameDirectory(manifestPath: string): string {
  const idx = manifestPath.lastIndexOf("/");
  return idx < 0 ? "" : manifestPath.slice(0, idx);
}

export function manifestFromJson(raw: unknown): FourDManifest {
  if (!raw || typeof raw !== "object") {
    throw new Error("Manifest must be an object");
  }
  const obj = raw as Record<string, unknown>;

  const version = Number(obj.version);
  if (!Number.isFinite(version) || version !== MANIFEST_VERSION) {
    throw new Error(`Unsupported manifest version: ${String(obj.version)}`);
  }

  const framesRaw = obj.frames;
  if (!Array.isArray(framesRaw)) {
    throw new Error("Manifest.frames must be an array");
  }

  const frames: SplatFrame[] = framesRaw.map((f, i) => {
    if (!f || typeof f !== "object") {
      throw new Error(`Frame ${i} is not an object`);
    }
    const entry = f as Record<string, unknown>;
    const url = String(entry.url ?? "");
    if (!url) throw new Error(`Frame ${i} has no url`);
    const timeSeconds = Number(entry.timeSeconds);
    if (!Number.isFinite(timeSeconds)) {
      throw new Error(`Frame ${i} has invalid timeSeconds`);
    }
    return { url, timeSeconds };
  });

  frames.sort((a, b) => a.timeSeconds - b.timeSeconds);

  return {
    version,
    durationSeconds: Number(obj.durationSeconds ?? 0),
    frames,
  };
}

export function parseManifestJson(raw: string): FourDManifest {
  return manifestFromJson(JSON.parse(raw));
}
