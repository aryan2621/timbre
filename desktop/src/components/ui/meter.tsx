import { cn } from "cn";

/**
 * A meter for bounded, comparable values (reference quality, disk usage).
 *
 * The old UI showed reference quality as bare text (`100/100`), which reads
 * as a typo next to a table of numbers. A meter makes the value scannable.
 */
export function Meter({
  value,
  max = 100,
  label,
  className,
  tone,
  showValue = true,
}: {
  value: number;
  max?: number;
  label?: string;
  className?: string;
  tone?: "auto" | "success" | "warning" | "danger";
  /** Print the raw value beside the bar; turn off when the caller shows its own label. */
  showValue?: boolean;
}) {
  const ratio = Math.max(0, Math.min(1, max ? value / max : 0));
  const percent = Math.round(ratio * 100);

  const resolved =
    tone === "auto" || !tone
      ? percent >= 80
        ? "success"
        : percent >= 50
          ? "warning"
          : "danger"
      : tone;

  const fills = {
    success: "bg-status-success",
    warning: "bg-status-warning",
    danger: "bg-destructive",
  } as const;

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div
        role="meter"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={label ?? "Value"}
        className="h-1.5 w-full min-w-16 overflow-hidden rounded-full bg-muted"
      >
        <div
          className={cn("h-full rounded-full transition-[width] duration-300 ease-out", fills[resolved])}
          style={{ width: `${percent}%` }}
        />
      </div>
      {showValue ? (
        <span
          data-numeric
          className="shrink-0 font-mono text-xs text-muted-foreground"
        >
          {Math.round(value)}
        </span>
      ) : null}
    </div>
  );
}
