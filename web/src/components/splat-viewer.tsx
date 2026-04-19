"use client";

import {
  Component,
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { OrbitControls, Splat } from "@react-three/drei";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";
import { frameIndexAt, type SplatFrame } from "@/lib/viewer/frames";
import {
  CAMERA_PRESETS,
  cameraPresetByKey,
  type CameraPresetKey,
} from "@/lib/viewer/camera-presets";
import { formatTimecode } from "@/lib/viewer/timecode";

export type { SplatFrame };

export type SplatViewerProps = {
  /** Single-frame (3D) source. Ignored when `frames` is provided. */
  src?: string;
  /** Time-varying (4D) frames, sorted by `timeSeconds`. */
  frames?: SplatFrame[];
  /** Whether 4D playback begins immediately. */
  initialPlaying?: boolean;
  className?: string;
};

export function SplatViewer({
  src,
  frames,
  initialPlaying = false,
  className,
}: SplatViewerProps) {
  const is4D = Boolean(frames && frames.length > 1);
  const duration = useMemo(() => {
    if (!frames || frames.length === 0) return 0;
    return frames[frames.length - 1].timeSeconds;
  }, [frames]);

  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(initialPlaying);
  const [loop, setLoop] = useState(true);
  const [preset, setPreset] = useState<CameraPresetKey>("iso");
  const [loaded, setLoaded] = useState(false);

  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef<number | null>(null);

  useEffect(() => {
    if (!playing || !is4D) return;
    const tick = (now: number) => {
      if (lastTickRef.current == null) lastTickRef.current = now;
      const dt = (now - lastTickRef.current) / 1000;
      lastTickRef.current = now;
      setTime((t) => {
        const next = t + dt;
        if (next >= duration) {
          if (loop) return next - duration;
          setPlaying(false);
          return duration;
        }
        return next;
      });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      lastTickRef.current = null;
    };
  }, [playing, duration, is4D, loop]);

  const togglePlay = useCallback(() => {
    setPlaying((p) => {
      if (!p && time >= duration) setTime(0);
      return !p;
    });
  }, [time, duration]);

  const step = useCallback(
    (delta: number) => {
      setPlaying(false);
      setTime((t) => Math.max(0, Math.min(duration, t + delta)));
    },
    [duration],
  );

  useEffect(() => {
    if (!is4D) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLElement) {
        const tag = e.target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA") return;
      }
      if (e.code === "Space") {
        e.preventDefault();
        togglePlay();
      } else if (e.code === "ArrowLeft") {
        step(e.shiftKey ? -1 : -0.1);
      } else if (e.code === "ArrowRight") {
        step(e.shiftKey ? 1 : 0.1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [is4D, togglePlay, step]);

  const currentSrc = useMemo(() => {
    if (!is4D || !frames) return src;
    const idx = frameIndexAt(frames, time);
    return frames[idx].url;
  }, [frames, time, is4D, src]);

  const presetConfig = cameraPresetByKey(preset);

  return (
    <div
      className={`relative w-full h-full rounded-xl overflow-hidden bg-black ${
        className ?? ""
      }`}
    >
      <ViewerErrorBoundary>
        <Canvas camera={{ position: [...presetConfig.position], fov: 50 }}>
          <color attach="background" args={["#05050a"]} />
          <Suspense fallback={null}>
            {currentSrc ? (
              <Splat
                key={currentSrc}
                src={currentSrc}
                onAfterRender={
                  loaded ? undefined : () => setLoaded(true)
                }
              />
            ) : null}
          </Suspense>
          <CameraPresetBinder preset={preset} />
          <OrbitControls
            enableDamping
            dampingFactor={0.1}
            rotateSpeed={0.6}
            zoomSpeed={0.9}
            panSpeed={0.6}
            makeDefault
            minDistance={0.3}
            maxDistance={25}
            target={[...presetConfig.target]}
          />
        </Canvas>
      </ViewerErrorBoundary>

      {!loaded && <LoadingOverlay />}

      <div className="absolute top-3 right-3 flex gap-1 pointer-events-auto">
        {CAMERA_PRESETS.map((p) => (
          <button
            key={p.key}
            type="button"
            onClick={() => setPreset(p.key)}
            aria-pressed={preset === p.key}
            className={`text-xs px-2 py-1 rounded-md transition-colors ${
              preset === p.key
                ? "bg-[color:var(--accent)] text-black"
                : "bg-black/50 text-white/80 hover:bg-black/70"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {is4D && (
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={togglePlay}
              className="btn btn-primary px-3 py-2 text-sm min-w-[4.5rem]"
              aria-label={playing ? "Pause" : "Play"}
            >
              {playing ? "Pause" : "Play"}
            </button>
            <input
              type="range"
              min={0}
              max={duration}
              step={0.01}
              value={time}
              onChange={(e) => {
                setPlaying(false);
                setTime(Number(e.target.value));
              }}
              className="flex-1 accent-[color:var(--accent)] cursor-pointer"
              aria-label="Timeline"
            />
            <span className="text-xs font-mono text-white/80 tabular-nums w-24 text-right">
              {formatTimecode(time)} / {formatTimecode(duration)}
            </span>
            <button
              type="button"
              onClick={() => setLoop((l) => !l)}
              aria-pressed={loop}
              title="Loop playback"
              className={`text-xs px-2 py-1 rounded-md transition-colors ${
                loop
                  ? "bg-[color:var(--accent)] text-black"
                  : "bg-black/50 text-white/80 hover:bg-black/70"
              }`}
            >
              Loop
            </button>
          </div>
          <p className="mt-2 text-[10px] text-white/40 font-mono">
            Space play · ←/→ step · Shift+arrow = 1s · Drag to orbit, scroll to zoom
          </p>
        </div>
      )}
    </div>
  );
}

function CameraPresetBinder({ preset }: { preset: CameraPresetKey }) {
  const { camera, controls } = useThree();
  useEffect(() => {
    const { position, target } = cameraPresetByKey(preset);
    camera.position.set(position[0], position[1], position[2]);
    camera.lookAt(target[0], target[1], target[2]);
    const orbit = controls as OrbitControlsImpl | null;
    if (orbit && "target" in orbit) {
      orbit.target.set(target[0], target[1], target[2]);
      orbit.update();
    }
  }, [preset, camera, controls]);
  return null;
}

function LoadingOverlay() {
  return (
    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 rounded-full border-2 border-white/20 border-t-[color:var(--accent)] animate-spin" />
        <p className="text-xs text-white/60">Loading memory…</p>
      </div>
    </div>
  );
}

type ErrorBoundaryState = { error: Error | null };

class ViewerErrorBoundary extends Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    // eslint-disable-next-line no-console
    console.error("SplatViewer error:", error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="absolute inset-0 flex items-center justify-center bg-black">
          <div className="text-center max-w-sm px-6">
            <p className="text-sm text-[color:var(--danger)] font-semibold">
              Couldn&apos;t render this memory
            </p>
            <p className="text-xs text-white/60 mt-2">
              {this.state.error.message || "Unknown rendering error."}
            </p>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="btn btn-ghost text-xs mt-4"
            >
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
