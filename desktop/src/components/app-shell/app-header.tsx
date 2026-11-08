import { motion } from "motion/react";
import { Moon, Search, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { useApp } from "@/lib/app-context";
import { useTheme } from "@/lib/theme";
import { formatShortcut } from "@/lib/shortcuts";
import { PAGE_TITLES } from "@/lib/pages";

/**
 * The application header.
 *
 * It used to be a 56px strip holding a breadcrumb and a duplicated status
 * pill. It now carries the global actions: the command palette trigger, the
 * theme switch, the engine status and the primary "new render" action.
 */
export function AppHeader() {
  const { page, setPaletteOpen } = useApp();
  const { resolvedTheme, setTheme } = useTheme();

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-3 border-b border-border/70 bg-background px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mx-0.5 h-5" />

      <div className="flex min-w-0 items-center gap-1.5 text-sm">
        <span className="hidden text-muted-foreground sm:inline">Timbre</span>
        <span className="hidden text-muted-foreground/40 sm:inline">/</span>
        <span className="truncate font-medium">{PAGE_TITLES[page]}</span>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="hidden h-8 items-center gap-2 rounded-md border border-border bg-surface-raised px-2.5 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground lg:flex"
        >
          <Search className="size-3.5" />
          <span>Search</span>
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[10px]">
            {formatShortcut("mod+k")}
          </kbd>
        </button>

        <Button
          variant="ghost"
          size="icon-sm"
          aria-label="Open the command palette"
          title={`Command palette · ${formatShortcut("mod+k")}`}
          onClick={() => setPaletteOpen(true)}
          className="lg:hidden"
        >
          <Search />
        </Button>

        <Button
          variant="ghost"
          size="icon-sm"
          aria-label={resolvedTheme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
          title="Toggle theme"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          <motion.span
            key={resolvedTheme}
            initial={{ opacity: 0, rotate: -35, scale: 0.8 }}
            animate={{ opacity: 1, rotate: 0, scale: 1 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            className="flex"
          >
            {resolvedTheme === "dark" ? <Sun /> : <Moon />}
          </motion.span>
        </Button>
      </div>
    </header>
  );
}

/** Kept for the collapsed-sidebar affordance in the sidebar header. */
