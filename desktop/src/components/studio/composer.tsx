import { ArrowUp, Loader2 } from "lucide-react";
import { forwardRef, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

export type StudioMode = "speech" | "sfx" | "music";

const MODES: { value: StudioMode; label: string }[] = [
  { value: "speech", label: "Speech" },
  { value: "sfx", label: "Sound effect" },
  { value: "music", label: "Music" },
];

interface ComposerProps {
  mode: StudioMode;
  onModeChange: (mode: StudioMode) => void;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  placeholder: string;
  canSubmit: boolean;
  busy: boolean;
  trailing?: string;
  maxLength?: number;
  controls?: ReactNode;
}

export const Composer = forwardRef<HTMLTextAreaElement, ComposerProps>(function Composer(
  { mode, onModeChange, value, onChange, onSubmit, placeholder, canSubmit, busy, trailing, maxLength, controls },
  ref,
) {
  return (
    <div className="rounded-lg border bg-card p-3">
      <Textarea
        ref={ref}
        value={value}
        rows={3}
        maxLength={maxLength}
        aria-label="Prompt"
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={(event) => {
          if (
            event.key === "Enter" &&
            !event.shiftKey &&
            !event.nativeEvent.isComposing &&
            event.keyCode !== 229
          ) {
            event.preventDefault();
            if (canSubmit) onSubmit();
          }
        }}
        className="min-h-16 resize-none border-0 bg-transparent px-1 shadow-none focus-visible:ring-0"
      />
      <div className="mt-2 flex items-center justify-between gap-3">
        <Tabs value={mode} onValueChange={(next) => onModeChange(next as StudioMode)}>
          <TabsList>
            {MODES.map((item) => (
              <TabsTrigger key={item.value} value={item.value}>
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
        <div className="flex items-center gap-3">
          {trailing ? <span className="hidden text-xs text-muted-foreground sm:inline">{trailing}</span> : null}
          {controls}
          <Button size="icon" aria-label="Generate" disabled={!canSubmit} onClick={onSubmit}>
            {busy ? <Loader2 className="animate-spin" /> : <ArrowUp />}
          </Button>
        </div>
      </div>
    </div>
  );
});

export function Suggestions({ items, onPick }: { items: string[]; onPick: (item: string) => void }) {
  return (
    <div className="mt-4 flex flex-wrap justify-center gap-2">
      {items.map((item) => (
        <button
          key={item}
          type="button"
          onClick={() => onPick(item)}
          className="max-w-xs truncate rounded-full bg-muted px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          {item}
        </button>
      ))}
    </div>
  );
}
