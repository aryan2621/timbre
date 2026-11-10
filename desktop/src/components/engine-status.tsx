import { Cpu } from "lucide-react";
import { cn } from "cn";
import { SoundBars } from "@/components/ui/sound-bars";
import { useEngineStatus } from "@/lib/engine-status";

export function EngineStatusBlock({ className }: { className?: string }) {
  const { status, device } = useEngineStatus();

  return (
    <div
      className={cn(
        "rounded-md border border-border bg-surface-raised p-3",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        {status === "connecting" ? (
          <SoundBars className="h-3 shrink-0 text-muted-foreground" />
        ) : (
          <span
            className={cn(
              "size-2 shrink-0 rounded-full",
              status === "online" ? "bg-status-success" : "bg-destructive",
            )}
          />
        )}
        <span className="text-xs font-medium">
          {status === "online"
            ? "Engine ready"
            : status === "offline"
              ? "Engine offline"
              : "Starting engine…"}
        </span>
      </div>

      {device ? (
        <div className="mt-2 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <Cpu className="size-3" />
          <span className="truncate" title={device.name}>
            {device.name}
          </span>
        </div>
      ) : null}
    </div>
  );
}
