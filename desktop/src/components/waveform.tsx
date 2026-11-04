import { useEffect, useRef, useState } from "react";
import { cn } from "cn";
import { useTheme } from "@/lib/theme";

interface WaveformProps {
  peaks?: number[] | null;
  progress?: number;
  onSeek?: (ratio: number) => void;
  className?: string;
  height?: number;
}

function resample(values: number[], count: number): number[] {
  if (!values.length) return [];
  if (values.length === count) return values;
  return Array.from({ length: count }, (_, i) => {
    const start = Math.floor((i / count) * values.length);
    const end = Math.max(start + 1, Math.floor(((i + 1) / count) * values.length));
    let max = 0;
    for (let j = start; j < end; j += 1) max = Math.max(max, values[j] ?? 0);
    return max;
  });
}

function cssColor(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim();
  return value || fallback;
}

export function Waveform({
  peaks,
  progress = 0,
  onSeek,
  className,
  height = 128,
}: WaveformProps) {
  const { resolvedTheme } = useTheme();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const observer = new ResizeObserver((entries) => {
      setWidth(entries[0]?.contentRect.width ?? 0);
    });
    observer.observe(host);
    setWidth(host.getBoundingClientRect().width);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width <= 0) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * dpr);
    canvas.height = Math.floor(height * dpr);
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    const mid = height / 2;
    const hasAudio = Boolean(peaks && peaks.length);
    const barColor = cssColor("--wave-bar", "#d4d4d4");
    const playedColor = cssColor("--wave-played", "#f6821f");
    const playheadColor = cssColor("--wave-playhead", "#1d1d1d");

    if (!hasAudio) {
      ctx.strokeStyle = barColor;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, mid);
      ctx.lineTo(width, mid);
      ctx.stroke();
      return;
    }

    const barWidth = 2;
    const gap = 1;
    const columns = Math.max(1, Math.floor(width / (barWidth + gap)));
    const values = resample(peaks ?? [], columns);
    const playedUntil = Math.max(0, Math.min(1, progress)) * width;

    values.forEach((value, index) => {
      const x = index * (barWidth + gap);
      const amplitude = Math.max(0, Math.min(1, value));
      const barHeight = Math.max(2, amplitude * height * 0.82);
      ctx.fillStyle = x <= playedUntil ? playedColor : barColor;
      // Rounded bar tops for a cleaner waveform look.
      ctx.beginPath();
      ctx.roundRect(x, mid - barHeight / 2, barWidth, barHeight, barWidth / 2);
      ctx.fill();
    });

    const playhead = Math.max(0, Math.min(width, playedUntil));
    ctx.fillStyle = playheadColor;
    ctx.fillRect(playhead - 1, 4, 2, height - 8);
  }, [peaks, progress, width, height, resolvedTheme]);

  const seek = (clientX: number) => {
    const host = hostRef.current;
    if (!host || !onSeek) return;
    const rect = host.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
    onSeek(ratio);
  };

  return (
    <div
      ref={hostRef}
      role="slider"
      aria-label="Audio waveform position"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(Math.max(0, Math.min(1, progress)) * 100)}
      tabIndex={onSeek ? 0 : -1}
      onClick={(event) => seek(event.clientX)}
      onKeyDown={(event) => {
        if (!onSeek) return;
        if (event.key === "ArrowLeft") onSeek(Math.max(0, progress - 0.02));
        if (event.key === "ArrowRight") onSeek(Math.min(1, progress + 0.02));
      }}
      className={cn(
        "relative w-full cursor-pointer overflow-hidden rounded-lg border border-border bg-[var(--wave-bg)] outline-none focus-visible:ring-2 focus-visible:ring-ring/30",
        className,
      )}
      style={{ height }}
    >
      <canvas ref={canvasRef} className="block" />
    </div>
  );
}
