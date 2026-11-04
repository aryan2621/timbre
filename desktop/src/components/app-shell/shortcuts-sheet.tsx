import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Kbd } from "@/components/ui/kbd";
import { SHORTCUTS, formatShortcut, type ShortcutGroup } from "@/lib/shortcuts";

const GROUP_ORDER: ShortcutGroup[] = ["Navigate", "Studio", "Library", "System"];

/** The keyboard reference, reachable from the palette and with `⇧?`. */
export function ShortcutsSheet({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="font-serif text-xl font-medium tracking-tight">
            Keyboard shortcuts
          </DialogTitle>
          <DialogDescription>
            The whole studio is reachable without the mouse.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 sm:grid-cols-2">
          {GROUP_ORDER.map((group) => (
            <section key={group} className="space-y-1.5">
              <h3 className="text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
                {group}
              </h3>
              {SHORTCUTS.filter((shortcut) => shortcut.group === group).map((shortcut) => (
                <div
                  key={shortcut.id}
                  className="flex items-center justify-between gap-3 rounded-lg px-2 py-1.5 text-sm transition-colors hover:bg-muted/60"
                >
                  <span className="text-muted-foreground">{shortcut.label}</span>
                  <Kbd>{formatShortcut(shortcut.combo)}</Kbd>
                </div>
              ))}
            </section>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
