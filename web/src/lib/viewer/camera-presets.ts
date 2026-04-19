export type Vec3 = readonly [number, number, number];

export type CameraPresetKey = "front" | "side" | "top" | "iso";

export type CameraPreset = {
  key: CameraPresetKey;
  label: string;
  position: Vec3;
  target: Vec3;
};

export const CAMERA_PRESETS: readonly CameraPreset[] = [
  {
    key: "front",
    label: "Front",
    position: [0, 0, 4],
    target: [0, 0, 0],
  },
  {
    key: "side",
    label: "Side",
    position: [4, 0, 0],
    target: [0, 0, 0],
  },
  {
    key: "top",
    label: "Top",
    position: [0, 4, 0.001],
    target: [0, 0, 0],
  },
  {
    key: "iso",
    label: "Iso",
    position: [3, 2.5, 3],
    target: [0, 0, 0],
  },
];

const PRESET_KEYS = CAMERA_PRESETS.map((p) => p.key);

export function isCameraPresetKey(value: unknown): value is CameraPresetKey {
  return typeof value === "string" && PRESET_KEYS.includes(value as CameraPresetKey);
}

export function cameraPresetByKey(key: CameraPresetKey): CameraPreset {
  const found = CAMERA_PRESETS.find((p) => p.key === key);
  if (!found) throw new Error(`Unknown camera preset: ${key}`);
  return found;
}
