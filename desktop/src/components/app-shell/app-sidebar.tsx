import {
  AudioLines,
  Boxes,
  History,
  Layers,
  Mic2,
  Search,
  Settings2,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import { EngineStatusBlock } from "@/components/engine-status";
import { formatShortcut } from "@/lib/shortcuts";
import type { PageKey } from "@/lib/pages";


interface NavItem {
  key: PageKey;
  label: string;
  icon: typeof AudioLines;
  shortcut: string;
}

const NAV_GROUPS: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Create",
    items: [
      { key: "studio", label: "Studio", icon: AudioLines, shortcut: "mod+1" },
      { key: "batch", label: "Batch", icon: Layers, shortcut: "mod+3" },
    ],
  },
  {
    label: "Library",
    items: [
      { key: "voices", label: "Voices", icon: Mic2, shortcut: "mod+2" },
      { key: "history", label: "History", icon: History, shortcut: "mod+4" },
    ],
  },
  {
    label: "System",
    items: [
      { key: "models", label: "Models", icon: Boxes, shortcut: "mod+5" },
      { key: "settings", label: "Settings", icon: Settings2, shortcut: "mod+6" },
    ],
  },
];

interface AppSidebarProps {
  page: PageKey;
  onNavigate: (page: PageKey) => void;
  onOpenPalette: () => void;
}

export function AppSidebar({ page, onNavigate, onOpenPalette }: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon" className="border-r border-border/70">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-1 py-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground shadow-[0_1px_2px_rgb(31_30_29/0.18)]">
            <AudioLines className="size-4" />
          </div>
          <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate font-serif text-[17px] font-medium tracking-tight">
              VoiceClone
            </span>
            <span className="truncate text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              Studio
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenPalette}
          className="group mx-1 mb-1 hidden h-8 items-center gap-2 rounded-md border border-border bg-surface-raised px-2 text-xs text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground group-data-[collapsible=icon]:hidden md:flex"
        >
          <Search className="size-3.5" />
          <span className="flex-1 text-left">Search…</span>
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[10px]">
            {formatShortcut("mod+k")}
          </kbd>
        </button>
      </SidebarHeader>

      <SidebarContent>
        {NAV_GROUPS.map((group) => (
          <SidebarGroup key={group.label}>
            <SidebarGroupLabel className="text-muted-foreground">
              {group.label}
            </SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.key}>
                    <SidebarMenuButton
                      isActive={page === item.key}
                      tooltip={`${item.label} · ${formatShortcut(item.shortcut)}`}
                      className="relative h-9"
                      onClick={() => onNavigate(item.key)}
                    >
                      {page === item.key ? (
                        <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />
                      ) : null}
                      <item.icon />
                      <span>{item.label}</span>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter>
        <EngineStatusBlock className="group-data-[collapsible=icon]:hidden" />
      </SidebarFooter>
    </Sidebar>
  );
}
