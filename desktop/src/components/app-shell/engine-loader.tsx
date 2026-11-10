import { useEffect, useState } from "react";

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
      <div className="w-72 space-y-4">
        <div className="space-y-1">
          <p className="text-base font-medium">Starting Timbre</p>
          <p className="text-sm text-muted-foreground">
            {slow ? "Still starting, this machine is slower than usual" : `${STEPS[step]}…`}
          </p>
        </div>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={Math.round(progress * 100)}
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
        >
          <div
            className="h-full rounded-full bg-primary transition-[width] duration-200 ease-out"
            style={{ width: `${Math.round(progress * 100)}%` }}
          />
        </div>
        <p className="text-xs tabular-nums text-muted-foreground">{Math.floor(elapsed)}s</p>
      </div>
    </div>
  );
}
