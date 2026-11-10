import { SoundBars } from "@/components/ui/sound-bars";

export function LoadingOverlay({ show, label }: { show: boolean; label?: string }) {
  if (!show) return null;
  return (
    <div
      role="status"
      aria-label={label ?? "Loading"}
      className="fixed inset-0 z-50 grid place-items-center bg-background/60 cursor-wait"
    >
      <div className="flex flex-col items-center gap-3">
        <SoundBars className="h-8 gap-1 [&>span]:w-1" />
        {label ? <p className="text-sm text-muted-foreground">{label}</p> : null}
      </div>
    </div>
  );
}
