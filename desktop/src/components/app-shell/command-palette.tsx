import { useEffect, useMemo, useState } from "react";
import {
  AudioLines,
  Boxes,
  Download,
  Eraser,
  FileUp,
  History,
  Keyboard,
  Layers,
  Mic2,
  Moon,
  PencilLine,
  Play,
  Plus,
  Settings2,
  Sun,
} from "lucide-react";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import { useApp } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { api } from "@/lib/api";
import { formatShortcut } from "@/lib/shortcuts";
import { PAGE_DESCRIPTIONS, PAGE_TITLES, type PageKey } from "@/lib/pages";
import type { VoiceProfile } from "@/lib/types";

const PAGE_ICONS: Record<PageKey, typeof AudioLines> = {
  studio: AudioLines,
  voices: Mic2,
  batch: Layers,
  history: History,
  models: Boxes,
  settings: Settings2,
};

const PAGE_SHORTCUTS: Record<PageKey, string> = {
  studio: "mod+1",
  voices: "mod+2",
  batch: "mod+3",
  history: "mod+4",
  models: "mod+5",
  settings: "mod+6",
};

/**
 * The command palette.
 *
 * The `command` primitive was already vendored in `components/ui` but never
 * mounted, which left the app with a set of invisible shortcuts. This makes
 * every capability reachable and discoverable from one place.
 */
export function CommandPalette() {
  const {
    paletteOpen,
    setPaletteOpen,
    navigate,
    actions,
    setShortcutsOpen,
    requestIntent,
  } = useApp();
  const { resolvedTheme, setTheme } = useTheme();
  const [voices, setVoices] = useState<VoiceProfile[]>([]);

  useEffect(() => {
    if (!paletteOpen) return;
    let cancelled = false;
    void api
      .listVoices()
      .then((next) => {
        if (!cancelled) setVoices(next);
      })
      .catch(() => {
        if (!cancelled) setVoices([]);
      });
    return () => {
      cancelled = true;
    };
  }, [paletteOpen]);

  const pages = useMemo(
    () =>
      (Object.keys(PAGE_TITLES) as PageKey[]).map((key) => ({
        key,
        label: PAGE_TITLES[key],
        description: PAGE_DESCRIPTIONS[key],
        icon: PAGE_ICONS[key],
      })),
    [],
  );

  const run = (action: () => void) => {
    setPaletteOpen(false);
    // Let the dialog close before the action changes the screen.
    window.setTimeout(action, 40);
  };

  return (
    <CommandDialog
      open={paletteOpen}
      onOpenChange={setPaletteOpen}
      title="Command palette"
      description="Search for a command, a page or a voice"
    >
      <CommandInput placeholder="Search commands, pages and voices…" />
      <CommandList>
        <CommandEmpty>
          <div className="flex flex-col items-center gap-1 py-2">
            <p className="text-sm font-medium">Nothing found</p>
            <p className="text-xs text-muted-foreground">
              Try a page name, an action, or a voice profile.
            </p>
          </div>
        </CommandEmpty>

        <CommandGroup heading="Studio">
          {actions.runSynthesis ? (
            <CommandItem
              value="run synthesis render"
              onSelect={() => run(() => actions.runSynthesis?.())}
            >
              <Play />
              Run synthesis
              <CommandShortcut>{formatShortcut("mod+enter")}</CommandShortcut>
            </CommandItem>
          ) : null}
          {actions.exportRender ? (
            <CommandItem
              value="export render audio wav"
              onSelect={() => run(() => actions.exportRender?.())}
            >
              <Download />
              Export the current render
              <CommandShortcut>{formatShortcut("mod+e")}</CommandShortcut>
            </CommandItem>
          ) : null}
          {actions.togglePlayback ? (
            <CommandItem
              value="play pause playback audio"
              onSelect={() => run(() => actions.togglePlayback?.())}
            >
              <AudioLines />
              Play / pause the render
              <CommandShortcut>{formatShortcut("space")}</CommandShortcut>
            </CommandItem>
          ) : null}
          {actions.focusScript ? (
            <CommandItem
              value="focus script editor text"
              onSelect={() => run(() => actions.focusScript?.())}
            >
              <PencilLine />
              Focus the script editor
              <CommandShortcut>{formatShortcut("mod+shift+t")}</CommandShortcut>
            </CommandItem>
          ) : null}
          {actions.clearScript ? (
            <CommandItem
              value="clear script text"
              onSelect={() => run(() => actions.clearScript?.())}
            >
              <Eraser />
              Clear the script
              <CommandShortcut>{formatShortcut("mod+backspace")}</CommandShortcut>
            </CommandItem>
          ) : null}
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Library">
          <CommandItem
            value="new voice profile create"
            onSelect={() =>
              run(() => {
                requestIntent("new-voice");
                navigate("voices");
              })
            }
          >
            <Plus />
            Create a voice profile
            <CommandShortcut>{formatShortcut("mod+shift+n")}</CommandShortcut>
          </CommandItem>
          <CommandItem
            value="import script batch file"
            onSelect={() =>
              run(() => {
                requestIntent("import-script");
                navigate("batch");
              })
            }
          >
            <FileUp />
            Import a batch script
            <CommandShortcut>{formatShortcut("mod+shift+i")}</CommandShortcut>
          </CommandItem>
        </CommandGroup>

        <CommandSeparator />

        <CommandGroup heading="Navigate">
          {pages.map((page) => (
            <CommandItem
              key={page.key}
              value={`go to ${page.label} ${page.description}`}
              onSelect={() => run(() => navigate(page.key))}
            >
              <page.icon />
              <span className="flex flex-col">
                <span>{page.label}</span>
                <span className="text-xs text-muted-foreground">
                  {page.description}
                </span>
              </span>
              <CommandShortcut>{formatShortcut(PAGE_SHORTCUTS[page.key])}</CommandShortcut>
            </CommandItem>
          ))}
        </CommandGroup>

        {voices.length ? (
          <>
            <CommandSeparator />
            <CommandGroup heading="Voices">
              {voices.map((voice) => (
                <CommandItem
                  key={voice.id}
                  value={`voice ${voice.name} ${voice.language}`}
                  onSelect={() => run(() => navigate("voices"))}
                >
                  <Mic2 />
                  <span className="flex flex-col">
                    <span>{voice.name}</span>
                    <span className="text-xs text-muted-foreground">
                      {voice.language.toUpperCase()} ·{" "}
                      {voice.clips.length} sample{voice.clips.length === 1 ? "" : "s"}
                    </span>
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        ) : null}

        <CommandSeparator />

        <CommandGroup heading="System">
          <CommandItem
            value="toggle theme light dark appearance"
            onSelect={() =>
              run(() => setTheme(resolvedTheme === "dark" ? "light" : "dark"))
            }
          >
            {resolvedTheme === "dark" ? <Sun /> : <Moon />}
            Switch to {resolvedTheme === "dark" ? "light" : "dark"} theme
          </CommandItem>
          <CommandItem
            value="keyboard shortcuts help"
            onSelect={() => run(() => setShortcutsOpen(true))}
          >
            <Keyboard />
            Keyboard shortcuts
            <CommandShortcut>{formatShortcut("shift+?")}</CommandShortcut>
          </CommandItem>
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
