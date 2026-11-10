import { cn } from "cn";

const DEFAULT_BARS = 5;

export function SoundBars({ className, count = DEFAULT_BARS }: { className?: string; count?: number }) {
  return (
    <span aria-hidden className={cn("inline-flex h-4 shrink-0 items-end gap-[2px] text-primary", className)}>
      {Array.from({ length: count }, (_, index) => (
        <span
          key={index}
          className="sound-bar w-[2px] rounded-full bg-current"
          style={{ animationDelay: `${(index * 120) % 900}ms` }}
        />
      ))}
    </span>
  );
}
