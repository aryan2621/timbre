import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import { cn } from "cn";
import { SoundBars } from "@/components/ui/sound-bars";

const EXPECTED_SECONDS = 15;
const STEPS = [
  "Unpacking the engine",
  "Loading audio libraries",
  "Starting the local server",
  "Loading your voices",
];

export function EngineLoader({ show }: { show: boolean }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!show) return;
    const started = Date.now();
    setElapsed(0);
    const timer = window.setInterval(() => setElapsed((Date.now() - started) / 1000), 200);
    return () => window.clearInterval(timer);
  }, [show]);

  if (!show) return null;
  const progress = 1 - Math.exp((-3 * elapsed) / EXPECTED_SECONDS);
  const step = Math.min(STEPS.length - 1, Math.floor(progress * STEPS.length));
  const slow = elapsed > EXPECTED_SECONDS * 2;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 z-50 grid place-items-center bg-background cursor-wait"
    >
      <div className="reveal-up flex w-80 flex-col items-center gap-8">
        <SoundBars count={28} className="h-14 gap-[3px] text-primary [&>span]:w-[3px]" />
        <div className="space-y-1 text-center">
          <p className="text-lg font-semibold tracking-tight">Timbre</p>
          <p className="text-sm text-muted-foreground">
            {slow ? "Still starting, this machine is slower than usual" : "Starting your local voice engine"}
          </p>
        </div>
        <ol className="w-full space-y-2 text-sm">
          {STEPS.map((label, index) => (
            <li
              key={label}
              className={cn(
                "flex items-center gap-3 transition-colors duration-150",
                index < step && "text-muted-foreground",
                index === step && "text-foreground",
                index > step && "text-muted-foreground/50",
              )}
            >
              <span className="grid h-4 w-6 shrink-0 place-items-center">
                {index < step ? (
                  <Check className="size-3.5 text-primary" />
                ) : index === step ? (
                  <SoundBars count={3} className="h-3 gap-[2px] [&>span]:w-[2px]" />
                ) : (
                  <span className="size-1 rounded-full bg-current" />
                )}
              </span>
              {label}
            </li>
          ))}
        </ol>
        <p className="text-xs tabular-nums text-muted-foreground">{Math.floor(elapsed)}s</p>
      </div>
    </div>
  );
}
