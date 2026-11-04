import {
  AudioLines,
  Boxes,
  History,
  Layers,
  Mic2,
  Settings2,
  ShieldCheck,
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

export type PageKey =
  | "studio"
  | "voices"
  | "batch"
  | "history"
  | "models"
  | "settings";

const NAV_ITEMS: Array<{
  key: PageKey;
  label: string;
  icon: typeof AudioLines;
}> = [
  { key: "studio", label: "Studio", icon: AudioLines },
  { key: "voices", label: "Voices", icon: Mic2 },
  { key: "batch", label: "Batch", icon: Layers },
  { key: "history", label: "History", icon: History },
  { key: "models", label: "Models", icon: Boxes },
  { key: "settings", label: "Settings", icon: Settings2 },
];

interface AppSidebarProps {
  page: PageKey;
  onNavigate: (page: PageKey) => void;
  online: boolean | null;
}

export function AppSidebar({ page, onNavigate, online }: AppSidebarProps) {
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2.5 px-1 py-2">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
            <AudioLines className="size-5" />
          </div>
          <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="truncate font-serif text-[17px] font-medium tracking-tight">
              VoiceClone
            </span>
            <span className="truncate text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Studio
            </span>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="text-muted-foreground">Workspace</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {NAV_ITEMS.map((item) => (
                <SidebarMenuItem key={item.key}>
                  <SidebarMenuButton
                    isActive={page === item.key}
                    tooltip={item.label}
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
      </SidebarContent>

      <SidebarFooter>
        <div className="flex items-center gap-2 rounded-lg bg-sidebar-accent/60 px-2.5 py-2 text-xs text-muted-foreground group-data-[collapsible=icon]:justify-center">
          <ShieldCheck className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <div className="grid min-w-0 leading-tight group-data-[collapsible=icon]:hidden">
            <span className="font-medium text-foreground">100% offline</span>
            <span className="flex items-center gap-1.5">
              <span
                className={`size-1.5 rounded-full ${
                  online === null
                    ? "bg-amber-500"
                    : online
                      ? "bg-emerald-500"
                      : "bg-red-500"
                }`}
              />
              {online === null
                ? "Connecting to engine"
                : online
                  ? "Engine connected"
                  : "Engine offline"}
            </span>
          </div>
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
