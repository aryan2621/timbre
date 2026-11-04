import { Loader2 } from "lucide-react";
import { cn } from "cn";

interface LoaderProps {
  className?: string;
  /** Spinner size utility class suffix, defaults to size-4. */
  size?: string;
}

/** Inline loader — spinner only, no visible text. */
export function Loader({ className, size = "size-4" }: LoaderProps) {
  return (
    <span
      role="status"
      aria-live="polite"
      aria-label="Loading"
      className={cn("inline-flex items-center justify-center", className)}
    >
      <Loader2 className={cn("animate-spin", size)} aria-hidden />
    </span>
  );
}
