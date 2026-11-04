import { motion } from "motion/react";
import { Layers } from "lucide-react";
import { cn } from "cn";
import { countWords } from "@/lib/chunk-preview";

/**
 * The sentence preview.
 *
 * Shows how the script will be split before the render starts. It removes
 * the "why did it take 40 seconds?" feeling and makes the render legible.
 */
export function SentenceChips({
  chunks,
  className,
}: {
  chunks: string[];
  className?: string;
}) {
  if (!chunks.length) return null;

  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
        <Layers className="size-3" />
        {chunks.length} sentence {chunks.length === 1 ? "chunk" : "chunks"}
      </div>
      <div className="flex flex-wrap gap-1.5">
        {chunks.map((chunk, index) => (
          <motion.span
            key={`${index}-${chunk.slice(0, 12)}`}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.18, delay: Math.min(index * 0.02, 0.2) }}
            className="group inline-flex max-w-full items-center gap-1.5 rounded-full border border-border bg-surface-inset px-2.5 py-1 text-[11.5px] text-muted-foreground"
            title={chunk}
          >
            <span className="font-mono text-[10px] text-primary/80">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span className="max-w-[22ch] truncate">{chunk}</span>
            <span className="font-mono text-[10px] opacity-60">
              {countWords(chunk)}w
            </span>
          </motion.span>
        ))}
      </div>
    </div>
  );
}
