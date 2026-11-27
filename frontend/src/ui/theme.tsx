import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type Theme = "light" | "dark";
export type FyTheme = Theme;

const STORAGE_KEY = "fyphub-theme";

/** Meta theme-color values (allowed outside CSS token file). */
const THEME_COLOR: Record<Theme, string> = {
  light: "#F5F7FB",
  dark: "#0D1117",
};

export function readStoredTheme(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "dark" || value === "light") return value;
  } catch {
    /* ignore */
  }
  return "light";
}

/** Apply theme via data-theme only — colours come from design-tokens.css. */
export function applyTheme(theme: Theme) {
  const root = document.documentElement;
  root.setAttribute("data-theme", theme);
  root.style.colorScheme = theme;
  let meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (!meta) {
    meta = document.createElement("meta");
    meta.name = "theme-color";
    document.head.appendChild(meta);
  }
  meta.content = THEME_COLOR[theme];
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* ignore */
  }
}

type ThemeContextValue = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() =>
    typeof document !== "undefined" ? readStoredTheme() : "light",
  );

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next);
    applyTheme(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((current) => {
      const next: Theme = current === "light" ? "dark" : "light";
      applyTheme(next);
      return next;
    });
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
}
