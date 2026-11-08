import {
  forwardRef,
  useEffect,
  useImperativeHandle,
  useRef,
  type CSSProperties,
} from "react";
import WaveSurfer from "wavesurfer.js";
import Timeline from "wavesurfer.js/plugins/timeline";
import Hover from "wavesurfer.js/plugins/hover";
import { cn } from "cn";
import { useTheme } from "@/lib/theme";

export interface WaveformPlayerHandle {
  playPause: () => void;
  stop: () => void;
  seekToRatio: (ratio: number) => void;
  skip: (seconds: number) => void;
  setVolume: (volume: number) => void;
  getCurrentTime: () => number;
  getDuration: () => number;
  isPlaying: () => boolean;
}

interface WaveformPlayerProps {
  url: string | null;
  /** Peaks from the backend, so the waveform renders without a second download. */
  peaks?: number[] | null;
  duration?: number;
  height?: number;
  timeline?: boolean;
  className?: string;
  onTimeUpdate?: (time: number) => void;
  onPlayChange?: (playing: boolean) => void;
  onReady?: (duration: number) => void;
  onEnded?: () => void;
}

function cssColor(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

function palette() {
  return {
    bar: cssColor("--wave-bar", "#d6d3c6"),
    played: cssColor("--wave-played", "#c96442"),
    playhead: cssColor("--wave-playhead", "#1f1e1d"),
    text: cssColor("--foreground", "#1f1e1d"),
    muted: cssColor("--muted-foreground", "#5e5d59"),
    overlay: cssColor("--popover", "#ffffff"),
  };
}

/**
 * The waveform surface.
 *
 * Replaces the hand-rolled canvas with wavesurfer.js: a real time ruler, a
 * hover scrub preview, click and drag seeking, zoom and the correct
 * playback clock. The player owns a single media element, so the transport
 * controls, the clock and the waveform can never disagree.
 */
export const WaveformPlayer = forwardRef<
  WaveformPlayerHandle,
  WaveformPlayerProps
>(function WaveformPlayer(
  {
    url,
    peaks,
    duration,
    height = 132,
    timeline = true,
    className,
    onTimeUpdate,
    onPlayChange,
    onReady,
    onEnded,
  },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const waveRef = useRef<WaveSurfer | null>(null);
  const requestRef = useRef<{ url: string | null; peaks?: number[] | null; duration?: number }>(
    { url: null },
  );
  const loadedUrlRef = useRef<string | null>(null);
  const { resolvedTheme } = useTheme();

  const callbacks = useRef({ onTimeUpdate, onPlayChange, onReady, onEnded });
  callbacks.current = { onTimeUpdate, onPlayChange, onReady, onEnded };

  useEffect(() => {
    requestRef.current = { url, peaks, duration };
  }, [url, peaks, duration]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const colors = palette();
    const wave = WaveSurfer.create({
      container,
      height,
      waveColor: colors.bar,
      progressColor: colors.played,
      cursorColor: colors.playhead,
      cursorWidth: 2,
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      hideScrollbar: true,
      dragToSeek: true,
      autoCenter: false,
      plugins: [
        ...(timeline
          ? [
              Timeline.create({
                height: 18,
                secondaryLabelOpacity: 0.35,
                style: {
                  fontSize: "10px",
                  fontFamily: "var(--font-mono)",
                  color: colors.muted,
                },
              }),
            ]
          : []),
        Hover.create({
          lineColor: colors.playhead,
          labelColor: colors.text,
          labelBackground: colors.overlay,
          labelSize: "11px",
        }),
      ],
    });

    waveRef.current = wave;
    loadedUrlRef.current = null;

    wave.on("timeupdate", (time: number) => callbacks.current.onTimeUpdate?.(time));
    wave.on("play", () => callbacks.current.onPlayChange?.(true));
    wave.on("pause", () => callbacks.current.onPlayChange?.(false));
    wave.on("finish", () => {
      callbacks.current.onPlayChange?.(false);
      callbacks.current.onEnded?.();
    });
    wave.on("ready", (loadedDuration: number) =>
      callbacks.current.onReady?.(loadedDuration),
    );
    wave.on("error", (error: unknown) => {
      console.error("Waveform failed to load", error);
    });

    const request = requestRef.current;
    if (request.url) {
      const channelData = request.peaks?.length
        ? [Float32Array.from(request.peaks)]
        : undefined;
      const knownDuration = request.duration ?? 0;
      if (channelData && knownDuration > 0) {
        void wave.load(request.url, channelData, knownDuration).catch(() => {});
      } else {
        void wave.load(request.url).catch(() => {});
      }
      loadedUrlRef.current = request.url;
    }

    return () => {
      wave.destroy();
      waveRef.current = null;
      loadedUrlRef.current = null;
    };
  }, [height, timeline, resolvedTheme]);

  useEffect(() => {
    const wave = waveRef.current;
    if (!wave || !url) return;
    if (loadedUrlRef.current === url) return;
    const channelData = peaks?.length ? [Float32Array.from(peaks)] : undefined;
    const knownDuration = duration ?? 0;
    if (channelData && knownDuration > 0) {
      void wave.load(url, channelData, knownDuration).catch(() => {});
    } else {
      void wave.load(url).catch(() => {});
    }
    loadedUrlRef.current = url;
  }, [url, peaks, duration]);

  useImperativeHandle(
    ref,
    () => ({
      playPause: () => {
        void waveRef.current?.playPause();
      },
      stop: () => {
        waveRef.current?.stop();
      },
      seekToRatio: (ratio: number) => {
        waveRef.current?.seekTo(Math.max(0, Math.min(1, ratio)));
      },
      skip: (seconds: number) => {
        waveRef.current?.skip(seconds);
      },
      setVolume: (volume: number) => {
        waveRef.current?.setVolume(Math.max(0, Math.min(1, volume)));
      },
      getCurrentTime: () => waveRef.current?.getCurrentTime() ?? 0,
      getDuration: () => waveRef.current?.getDuration() ?? 0,
      isPlaying: () => waveRef.current?.isPlaying() ?? false,
    }),
    [],
  );

  return (
    <div
      ref={containerRef}
      className={cn(
        "w-full overflow-hidden rounded-md border border-border bg-surface-inset",
        className,
      )}
      style={{ ["--waveform-height" as string]: `${height}px` } as CSSProperties}
    />
  );
});
