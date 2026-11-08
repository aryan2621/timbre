import {
  AudioLines,
  Boxes,
  History,
  ArrowLeft,
  Bot,
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
import { Input } from "@/components/ui/input";
import { SETTINGS_SECTIONS } from "@/hooks/use-settings";
import { settingsNav, useSettingsNav } from "@/lib/settings-nav";
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
      { key: "agents", label: "Agents", icon: Bot, shortcut: "mod+7" },
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

function SettingsNavigation({ onNavigate }: { onNavigate: (page: PageKey) => void }) {
  const { activeSection, search, returnPage } = useSettingsNav();
  const term = search.trim().toLowerCase();
  const sections = term
    ? SETTINGS_SECTIONS.filter((section) =>
        `${section.label} ${section.description}`.toLowerCase().includes(term),
      )
    : SETTINGS_SECTIONS;
  return (
    <SidebarContent>
      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton className="h-9" tooltip="Back" onClick={() => onNavigate(returnPage)}>
                <ArrowLeft />
                <span>Back</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
          <Input
            value={search}
            onChange={(event) => settingsNav.setSearch(event.target.value)}
            placeholder="Find a setting"
            aria-label="Search the settings"
            className="my-2 group-data-[collapsible=icon]:hidden"
          />
          <SidebarMenu>
            {sections.map((section) => (
              <SidebarMenuItem key={section.id}>
                <SidebarMenuButton
                  isActive={section.id === activeSection}
                  tooltip={section.label}
                  className="h-9"
                  onClick={() => settingsNav.setActiveSection(section.id)}
                >
                  <section.icon />
                  <span>{section.label}</span>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>
  );
}

export function AppSidebar({ page, onNavigate, onOpenPalette }: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon" className="border-r border-border/70">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-1 py-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <AudioLines className="size-4" />
          </div>
          <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate text-[15px] font-semibold tracking-tight">Timbre</span>
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

      {page === "settings" ? (
        <SettingsNavigation onNavigate={onNavigate} />
      ) : (
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
                      className="h-9"
                      onClick={() => onNavigate(item.key)}
                    >
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
      )}

      <SidebarFooter>
        <EngineStatusBlock className="group-data-[collapsible=icon]:hidden" />
      </SidebarFooter>
    </Sidebar>
  );
}
