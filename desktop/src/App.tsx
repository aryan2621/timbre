import { Suspense, lazy, useEffect, useState } from "react";
import { cn } from "cn";
import { AppSidebar, type PageKey } from "@/components/app-sidebar";
import { Separator } from "@/components/ui/separator";
import {
  SidebarInset,
  SidebarProvider,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Loader } from "@/components/ui/loader";
import { checkHealth } from "@/lib/api";
import { ThemeProvider } from "@/lib/theme";

// Route-level code splitting: each page is only downloaded when first visited,
// keeping the initial studio bundle lean and startup fast.
const StudioPage = lazy(() => import("@/pages/studio").then((m) => ({ default: m.StudioPage })));
const VoicesPage = lazy(() => import("@/pages/voices").then((m) => ({ default: m.VoicesPage })));
const BatchPage = lazy(() => import("@/pages/batch").then((m) => ({ default: m.BatchPage })));
const HistoryPage = lazy(() => import("@/pages/history").then((m) => ({ default: m.HistoryPage })));
const ModelsPage = lazy(() => import("@/pages/models").then((m) => ({ default: m.ModelsPage })));
const SettingsPage = lazy(() => import("@/pages/settings").then((m) => ({ default: m.SettingsPage })));

const PAGE_TITLES: Record<PageKey, string> = {
  studio: "Studio",
  voices: "Voices",
  batch: "Batch",
  history: "History",
  models: "Models",
  settings: "Settings",
};

function Shell() {
  const [page, setPage] = useState<PageKey>("studio");
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    const ping = async () => {
      const next = await checkHealth();
      if (active) setOnline(next);
    };
    void ping();
    const timer = window.setInterval(() => void ping(), 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.altKey) return;
      const map: Record<string, PageKey> = {
        "1": "studio",
        "2": "voices",
        "3": "batch",
        "4": "history",
        "5": "models",
        "6": "settings",
      };
      const target = map[event.key];
      if (target) {
        event.preventDefault();
        setPage(target);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const meta = PAGE_TITLES[page];
  // When the Settings dialog is open, the Studio page stays visible underneath it.
  const contentPage: PageKey = page === "settings" ? "studio" : page;

  return (
    <SidebarProvider>
      <AppSidebar page={page} onNavigate={setPage} online={online} />

      <SidebarInset className="min-w-0">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b border-border bg-card/95 px-4 backdrop-blur-sm">
          <SidebarTrigger className="-ml-1" />
          <Separator orientation="vertical" className="mx-1 h-5" />
          <div className="flex min-w-0 items-center gap-1.5 text-sm">
            <span className="hidden text-muted-foreground sm:inline">VoiceClone</span>
            <span className="hidden text-muted-foreground/40 sm:inline">/</span>
            <span className="truncate font-medium">{meta}</span>
          </div>

          <div className="ml-auto flex items-center gap-2">
            <span className="inline-flex items-center gap-2 rounded-md border border-border bg-card px-2.5 py-1 text-xs font-medium">
              <span
                className={cn(
                  "size-1.5 rounded-full",
                  online === null
                    ? "animate-pulse bg-amber-500"
                    : online
                      ? "bg-emerald-500"
                      : "bg-red-500",
                )}
              />
              <span className={online === false ? "text-destructive" : "text-foreground"}>
                {online === null
                  ? "Connecting"
                  : online
                    ? "Engine online"
                    : "Demo mode"}
              </span>
            </span>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto p-4 md:p-6">
          <Suspense
            fallback={
              <div className="flex h-[50vh] items-center justify-center">
                <Loader size="size-6" />
              </div>
            }
          >
            {contentPage === "studio" && <StudioPage online={online} />}
            {contentPage === "voices" && <VoicesPage online={online} />}
            {contentPage === "batch" && <BatchPage online={online} />}
            {contentPage === "history" && <HistoryPage online={online} />}
            {contentPage === "models" && <ModelsPage online={online} />}
          </Suspense>
        </div>
      </SidebarInset>

      {page === "settings" && (
        <Suspense fallback={null}>
          <SettingsPage
            open={page === "settings"}
            onClose={() => setPage("studio")}
            online={online}
          />
        </Suspense>
      )}
    </SidebarProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <TooltipProvider delay={300}>
        <Shell />
        <Toaster richColors position="bottom-right" closeButton />
      </TooltipProvider>
    </ThemeProvider>
  );
}
