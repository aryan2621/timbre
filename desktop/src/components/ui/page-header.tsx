import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "cn";

/**
 * The one page header in the app.
 *
 * The old app had four different header implementations (two serif, two sans,
 * with and without a divider). Every screen now renders this component, so
 * the type scale and rhythm are identical everywhere.
 */
interface PageHeaderProps {
  title: string;
  description?: ReactNode;
  eyebrow?: ReactNode;
  icon?: LucideIcon;
  actions?: ReactNode;
  /** Small read-only facts shown next to the title. */
  meta?: ReactNode;
  className?: string;
}

export function PageHeader({
  title,
  description,
  eyebrow,
  icon: Icon,
  actions,
  meta,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={cn(
        "flex flex-col gap-3 border-b border-border/70 pb-4 md:flex-row md:items-end md:justify-between",
        className,
      )}
    >
      <div className="min-w-0">
        {eyebrow ? (
          <div className="mb-1.5 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {eyebrow}
          </div>
        ) : null}
        <div className="flex items-center gap-2.5">
          {Icon ? (
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-accent text-primary">
              <Icon className="size-4" />
            </span>
          ) : null}
          <h1 className="truncate font-serif text-[28px] font-medium leading-tight tracking-tight">
            {title}
          </h1>
        </div>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
            {description}
          </p>
        ) : null}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        {meta}
        {actions}
      </div>
    </header>
  );
}

/** A read-only fact chip used in page headers and toolbars. */
export function StatChip({
  icon: Icon,
  children,
  tone = "neutral",
  className,
}: {
  icon?: LucideIcon;
  children: ReactNode;
  tone?: "neutral" | "accent" | "success" | "warning";
  className?: string;
}) {
  const tones = {
    neutral: "border-border bg-surface-raised text-muted-foreground",
    accent: "border-primary/25 bg-surface-accent text-primary",
    success: "border-status-success/30 bg-status-success/10 text-status-success",
    warning: "border-status-warning/35 bg-status-warning/10 text-status-warning",
  } as const;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
        tones[tone],
        className,
      )}
    >
      {Icon ? <Icon className="size-3.5" /> : null}
      {children}
    </span>
  );
}
