"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { OrbitControls, Splat } from "@react-three/drei";
import { frameIndexAt, type SplatFrame } from "@/lib/viewer/frames";

export type { SplatFrame };

export type SplatViewerProps = {
  /** Single-frame (3D) source. Ignored if `frames` is provided. */
  src?: string;
  /** Time-varying (4D) frames. Higher-index frames play later. */
  frames?: SplatFrame[];
  /** Initial playback rate for 4D playback, default 1x. */
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
  }, [playing, duration, is4D]);

  const currentSrc = useMemo(() => {
    if (!is4D || !frames) return src;
    const idx = frameIndexAt(frames, time);
    return frames[idx].url;
  }, [frames, time, is4D, src]);

  return (
    <div
      className={`relative w-full h-full rounded-xl overflow-hidden bg-black ${
        className ?? ""
      }`}
    >
      <Canvas camera={{ position: [0, 0, 4], fov: 50 }}>
        <color attach="background" args={["#05050a"]} />
        <Suspense fallback={null}>
          {currentSrc ? <Splat src={currentSrc} /> : null}
        </Suspense>
        <OrbitControls
          enableDamping
          dampingFactor={0.08}
          makeDefault
          minDistance={0.5}
          maxDistance={20}
        />
      </Canvas>
      {is4D && (
        <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => {
                if (time >= duration) setTime(0);
                setPlaying((p) => !p);
              }}
              className="btn btn-primary px-3 py-2 text-sm"
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
              className="flex-1 accent-[color:var(--accent)]"
              aria-label="Timeline"
            />
            <span className="text-xs font-mono text-white/80 w-16 text-right">
              {time.toFixed(1)}s / {duration.toFixed(1)}s
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

