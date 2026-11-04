import { motion } from "motion/react";
import { CircleCheck, CircleDashed, CircleX, Cpu } from "lucide-react";
import { cn } from "cn";
import { useEngineStatus } from "@/lib/engine-status";

/**
 * The single rendering of the engine connection state.
 *
 * Previously the header showed "Engine online" while the sidebar footer said
 * "100% offline / Engine connected" at the same time. There is now one
 * status, one component and one wording.
 */
export function EngineStatusPill({
  className,
  showLabel = true,
}: {
  className?: string;
  showLabel?: boolean;
}) {
  const { status, device, checking } = useEngineStatus();

  const config = {
    online: {
      label: "Engine ready",
      icon: CircleCheck,
      dot: "bg-status-success",
      text: "text-foreground",
    },
    offline: {
      label: "Engine offline",
      icon: CircleX,
      dot: "bg-destructive",
      text: "text-destructive",
    },
    connecting: {
      label: "Connecting",
      icon: CircleDashed,
      dot: "bg-status-warning",
      text: "text-muted-foreground",
    },
  }[status];

  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full border border-border bg-surface-raised px-2.5 py-1 text-xs font-medium shadow-[0_1px_2px_rgb(31_30_29/0.04)]",
        className,
      )}
      title={device ? `${device.name}` : undefined}
    >
      <span className="relative flex size-2 items-center justify-center">
        <span className={cn("size-2 rounded-full", config.dot)} />
        {status === "connecting" || checking ? (
          <motion.span
            className="absolute inset-0 rounded-full bg-status-warning/40"
            animate={{ scale: [1, 2.2], opacity: [0.6, 0] }}
            transition={{ duration: 1.4, repeat: Infinity, ease: "easeOut" }}
          />
        ) : null}
      </span>
      {showLabel ? (
        <span className={cn("inline-flex items-center gap-1.5", config.text)}>
          <Icon className="size-3.5" />
          {config.label}
        </span>
      ) : null}
    </span>
  );
}

/** The sidebar footer block — status, device and a one-line privacy note. */
export function EngineStatusBlock({ className }: { className?: string }) {
  const { status, device } = useEngineStatus();

  return (
    <div
      className={cn(
        "rounded-xl border border-border bg-surface-raised p-3 shadow-[0_1px_2px_rgb(31_30_29/0.04)]",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "size-2 shrink-0 rounded-full",
            status === "online"
              ? "bg-status-success"
              : status === "offline"
                ? "bg-destructive"
                : "bg-status-warning",
          )}
        />
        <span className="text-xs font-medium">
          {status === "online"
            ? "Engine ready"
            : status === "offline"
              ? "Engine offline"
              : "Connecting…"}
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

      <p className="mt-2 border-t border-border/70 pt-2 text-[11px] leading-snug text-muted-foreground">
        Everything runs on this machine. No account, no upload, no telemetry.
      </p>
    </div>
  );
}
