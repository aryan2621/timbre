import { useMemo, useState } from "react";
import { CheckCircle2, Mic2, Search } from "lucide-react";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import { cn } from "cn";
import type { VoiceProfile } from "@/lib/types";

interface VoicePickerProps {
  voices: VoiceProfile[];
  value: VoiceProfile | null;
  onChange: (voice: VoiceProfile) => void;
  className?: string;
  disabled?: boolean;
}

/**
 * The voice selector.
 *
 * The old select showed a bare name and an ISO code. This one is searchable,
 * shows the reference quality, the sample count and the consent state, and
 * keeps the current selection visible.
 */
export function VoicePicker({
  voices,
  value,
  onChange,
  className,
  disabled,
}: VoicePickerProps) {
  const [query, setQuery] = useState("");

  const sorted = useMemo(
    () => [...voices].sort((a, b) => a.name.localeCompare(b.name)),
    [voices],
  );

  return (
    <Combobox
      items={sorted}
      value={value}
      onValueChange={(voice) => {
        if (voice) onChange(voice);
      }}
      onInputValueChange={(inputValue) => setQuery(inputValue)}
      filter={(voice, search) => {
        const term = search.trim().toLowerCase();
        if (!term) return true;
        return (
          voice.name.toLowerCase().includes(term) ||
          voice.language.toLowerCase().includes(term) ||
          voice.notes.toLowerCase().includes(term)
        );
      }}
      itemToStringLabel={(voice) => voice.name}
      isItemEqualToValue={(a, b) => a.id === b.id}
      disabled={disabled}
    >
      <ComboboxInput
        placeholder="Search voice profiles"
        aria-label="Reference voice profile"
        className={cn("w-full", className)}
      />
      <ComboboxContent>
        <ComboboxEmpty>
          <div className="flex flex-col items-center gap-1 py-3 text-center">
            <Search className="size-4 text-muted-foreground/60" />
            <p className="text-sm font-medium">No voice matches “{query}”</p>
            <p className="text-xs text-muted-foreground">
              Create a profile from the Voices screen.
            </p>
          </div>
        </ComboboxEmpty>
        <ComboboxList>
          {(voice: VoiceProfile) => {
            return (
              <ComboboxItem key={voice.id} value={voice} className="gap-2.5 py-2">
                <span className="flex size-7 shrink-0 items-center justify-center rounded-md bg-surface-accent text-primary">
                  <Mic2 className="size-3.5" />
                </span>
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{voice.name}</span>
                  <span className="truncate text-xs text-muted-foreground">
                    {voice.language.toUpperCase()} · {voice.clips.length} sample
                    {voice.clips.length === 1 ? "" : "s"}
                  </span>
                </span>
                {voice.consent_confirmed ? (
                  <CheckCircle2 className="ml-auto size-3.5 shrink-0 text-status-success" />
                ) : null}
              </ComboboxItem>
            );
          }}
        </ComboboxList>
      </ComboboxContent>
    </Combobox>
  );
}
