import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme = "dark" | "light" | "system";
export type ResolvedTheme = "dark" | "light";

interface ThemeContextValue {
  theme: Theme;
  resolvedTheme: ResolvedTheme;
  setTheme: (theme: Theme) => void;
}

const STORAGE_KEY = "voiceclone-theme-v2";

const ThemeContext = createContext<ThemeContextValue | null>(null);

function prefersLight(): boolean {
  return window.matchMedia("(prefers-color-scheme: light)").matches;
}

function resolve(theme: Theme): ResolvedTheme {
  if (theme === "system") return prefersLight() ? "light" : "dark";
  return theme;
}

function apply(theme: Theme): ResolvedTheme {
  const resolved = resolve(theme);
  const root = document.documentElement;
  root.classList.toggle("dark", resolved === "dark");
  root.setAttribute("data-theme", resolved);
  root.style.colorScheme = resolved;
  return resolved;
}

function readStoredTheme(): Theme {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch {
    /* localStorage can be unavailable under strict file:// policies */
  }
  return "light";
}

/** Applies the persisted theme before React mounts to avoid a light flash. */
export function applyStoredTheme(): void {
  apply(readStoredTheme());
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(readStoredTheme);
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() =>
    resolve(readStoredTheme()),
  );

  useEffect(() => {
    setResolvedTheme(apply(theme));
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      /* persistence is best-effort */
    }
  }, [theme]);

  useEffect(() => {
    if (theme !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: light)");
    const onChange = () => setResolvedTheme(apply("system"));
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme]);

  const value = useMemo<ThemeContextValue>(
    () => ({ theme, resolvedTheme, setTheme }),
    [theme, resolvedTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return context;
}
