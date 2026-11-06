/**
 * Formatting helpers shared by every screen.
 *
 * The UI used to format values inline in each page, which is why durations
 * read `7.23s` in one place and `0:07` nowhere. Every user-visible value now
 * goes through this module so the whole app speaks the same language.
 */

/** Narrows a nullable number to a safe, finite number. */
function safeNumber(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/** `83.4` -> `1:23` (minutes:seconds, always at least `0:00`). */
export function formatDuration(seconds: number | null | undefined): string {
  const value = safeNumber(seconds);
  if (value === null || value < 0) return "0:00";
  const total = Math.floor(value);
  const mins = Math.floor(total / 60);
  const secs = total % 60;
  return `${mins}:${String(secs).padStart(2, "0")}`;
}

/** `83.456` -> `1:23.5`, for the transport readout where precision helps. */
export function formatTimecode(seconds: number | null | undefined): string {
  const value = safeNumber(seconds);
  if (value === null || value < 0) return "0:00.0";
  const mins = Math.floor(value / 60);
  const rest = value % 60;
  return `${mins}:${rest.toFixed(1).padStart(4, "0")}`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (!bytes) return "—";
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(2)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(0)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${bytes} B`;
}

/** "just now" / "12m ago" / "Nov 4" — relative first, absolute on demand. */
export function formatRelativeDate(value: string | number | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  const delta = Date.now() - date.getTime();
  const minutes = Math.round(delta / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function formatAbsoluteDate(value: string | number | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Rough spoken-duration estimate: ~150 words per minute, scaled by speed. */
export function estimateDurationSeconds(words: number, speed = 1): number {
  if (!words) return 0;
  return (words / 150) * 60 / Math.max(0.1, speed);
}
