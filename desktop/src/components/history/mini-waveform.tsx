import { useMemo } from "react";
import { cn } from "cn";

/**
 * A tiny waveform strip.
 *
 * The History table draws one of these per row so a take can be recognised
 * by its shape, not only by its timestamp. It is SVG rather than canvas so
 * it stays crisp on retina displays and costs nothing to scale.
 */
export function MiniWaveform({
  peaks,
  progress = 0,
  className,
  height = 24,
  bars = 48,
}: {
  peaks: number[] | null | undefined;
  progress?: number;
  className?: string;
  height?: number;
  bars?: number;
}) {
  const columns = useMemo(() => {
    if (!peaks?.length) return [];
    const step = peaks.length / bars;
    const result: number[] = [];
    for (let index = 0; index < bars; index += 1) {
      const start = Math.floor(index * step);
      const end = Math.max(start + 1, Math.floor((index + 1) * step));
      let max = 0;
      for (let cursor = start; cursor < end && cursor < peaks.length; cursor += 1) {
        max = Math.max(max, peaks[cursor] ?? 0);
      }
      result.push(max);
    }
    return result;
  }, [bars, peaks]);

  if (!columns.length) {
    return (
      <div
        className={cn("rounded bg-muted/70", className)}
        style={{ height }}
        aria-hidden
      />
    );
  }

  const played = Math.round(columns.length * Math.max(0, Math.min(1, progress)));

  return (
    <svg
      className={cn("w-full overflow-visible", className)}
      height={height}
      viewBox={`0 0 ${columns.length} 1`}
      preserveAspectRatio="none"
      role="img"
      aria-label="Waveform preview"
    >
      {columns.map((value, index) => {
        const barHeight = Math.max(0.08, value);
        return (
          <rect
            key={index}
            x={index}
            y={(1 - barHeight) / 2}
            width={0.62}
            height={barHeight}
            rx={0.3}
            className={index < played ? "fill-primary" : "fill-border"}
          />
        );
      })}
    </svg>
  );
}
