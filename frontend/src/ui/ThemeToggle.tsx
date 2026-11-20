import { Moon, Sun } from "lucide-react";
import { useTheme } from "./theme";

type ThemeToggleProps = {
  className?: string;
};

export function ThemeToggle({ className = "" }: ThemeToggleProps) {
  const { theme, toggleTheme } = useTheme();
  const nextLabel = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
  return (
    <button
      type="button"
      className={`fy-theme-toggle ${className}`.trim()}
      aria-label={nextLabel}
      title={nextLabel}
      onClick={toggleTheme}
    >
      {theme === "light" ? (
        <Moon aria-hidden="true" strokeWidth={1.75} size={18} />
      ) : (
        <Sun aria-hidden="true" strokeWidth={1.75} size={18} />
      )}
    </button>
  );
}
