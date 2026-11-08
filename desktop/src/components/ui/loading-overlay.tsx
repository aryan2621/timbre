import { Loader2 } from "lucide-react";

export function LoadingOverlay({ show }: { show: boolean }) {
  if (!show) return null;
  return (
    <div
      role="status"
      aria-label="Loading"
      className="fixed inset-0 z-50 grid place-items-center bg-background/60 cursor-wait"
    >
      <Loader2 className="size-8 animate-spin text-muted-foreground" />
    </div>
  );
}
