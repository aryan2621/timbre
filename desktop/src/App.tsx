import { Suspense, lazy, useEffect, useMemo } from "react";
import { motion } from "motion/react";
import { settingsNav } from "@/lib/settings-nav";
import { AppSidebar } from "@/components/app-shell/app-sidebar";
import { AppHeader } from "@/components/app-shell/app-header";
import { CommandPalette } from "@/components/app-shell/command-palette";
import { ShortcutsSheet } from "@/components/app-shell/shortcuts-sheet";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { EngineLoader } from "@/components/app-shell/engine-loader";
import { AppProvider, useApp } from "@/lib/app-context";
import { EngineStatusProvider, useEngineStatus } from "@/lib/engine-status";
import { ThemeProvider, useTheme } from "@/lib/theme";
import { useHashRoute } from "@/lib/use-router";
import { useHotkeys } from "@/lib/use-hotkeys";
import { NAVIGATION_SHORTCUTS } from "@/lib/shortcuts";
import { pageVariants } from "@/lib/motion";

// Route-level code splitting: each page is only downloaded when first visited,
// keeping the initial studio bundle lean and startup fast.
const StudioPage = lazy(() => import("@/pages/studio").then((m) => ({ default: m.StudioPage })));
const VoicesPage = lazy(() => import("@/pages/voices").then((m) => ({ default: m.VoicesPage })));
const BatchPage = lazy(() => import("@/pages/batch").then((m) => ({ default: m.BatchPage })));
const AgentsPage = lazy(() => import("@/pages/agents").then((m) => ({ default: m.AgentsPage })));
const HistoryPage = lazy(() => import("@/pages/history").then((m) => ({ default: m.HistoryPage })));
const ModelsPage = lazy(() => import("@/pages/models").then((m) => ({ default: m.ModelsPage })));
const SettingsPage = lazy(() => import("@/pages/settings").then((m) => ({ default: m.SettingsPage })));

function PageSkeleton() {
  return (
    <div className="space-y-4">
      <div className="space-y-2 border-b border-border/70 pb-4">
        <Skeleton className="h-7 w-56" />
        <Skeleton className="h-4 w-80" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Skeleton className="h-40 lg:col-span-2" />
        <Skeleton className="h-40" />
      </div>
      <Skeleton className="h-56" />
    </div>
  );
}

function Shell() {
  const {
    page,
    navigate,
    setPaletteOpen,
    setShortcutsOpen,
    shortcutsOpen,
    requestIntent,
  } = useApp();
  const { setTheme, resolvedTheme } = useTheme();

  useHotkeys(
    useMemo(
      () => ({
        "mod+k": () => setPaletteOpen(true),
        "shift+?": () => setShortcutsOpen(true),
        "mod+shift+l": () =>
          setTheme(resolvedTheme === "dark" ? "light" : "dark"),
        "mod+shift+n": () => {
          requestIntent("new-voice");
          navigate("voices");
        },
        "mod+shift+i": () => {
          requestIntent("import-script");
          navigate("batch");
        },
        ...Object.fromEntries(
          Object.entries(NAVIGATION_SHORTCUTS).map(([combo, target]) => [
            combo,
            () => navigate(target),
          ]),
        ),
      }),
      [
        navigate,
        requestIntent,
        resolvedTheme,
        setPaletteOpen,
        setShortcutsOpen,
        setTheme,
      ],
    ),
  );

  useEffect(() => {
    if (page !== "settings") settingsNav.setReturnPage(page);
  }, [page]);

  // Keep the document title in sync with the current screen.
  useEffect(() => {
    document.title = `Timbre · ${page.charAt(0).toUpperCase()}${page.slice(1)}`;
  }, [page]);

  const { status } = useEngineStatus();

  return (
    <SidebarProvider>
      <EngineLoader show={status === "connecting"} />
      <AppSidebar
        page={page}
        onNavigate={navigate}
        onOpenPalette={() => setPaletteOpen(true)}
      />

      <SidebarInset className="min-w-0">
        <AppHeader />

        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-[1440px] p-4 md:p-6">
              <motion.div
                key={page}
                variants={pageVariants}
                initial="initial"
                animate="animate"
              >
                <Suspense fallback={<PageSkeleton />}>
                  {page === "studio" && <StudioPage />}
                  {page === "voices" && <VoicesPage />}
                  {page === "batch" && <BatchPage />}
                  {page === "agents" && <AgentsPage />}
                  {page === "history" && <HistoryPage />}
                  {page === "models" && <ModelsPage />}
                  {page === "settings" && <SettingsPage />}
                </Suspense>
              </motion.div>
          </div>
        </main>
      </SidebarInset>

      <CommandPalette />
      <ShortcutsSheet open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </SidebarProvider>
  );
}

function Routed() {
  const [page, navigate] = useHashRoute();
  return (
    <AppProvider page={page} navigate={navigate}>
      <Shell />
    </AppProvider>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <EngineStatusProvider>
        <TooltipProvider delay={300}>
          <Routed />
          <Toaster richColors position="bottom-right" closeButton />
        </TooltipProvider>
      </EngineStatusProvider>
    </ThemeProvider>
  );
}
