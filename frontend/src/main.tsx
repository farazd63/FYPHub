import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource/ibm-plex-sans/400.css";
import "@fontsource/ibm-plex-sans/600.css";
import "@fontsource/ibm-plex-sans/700.css";
import App from "./App";
import { ThemeProvider } from "./ui/theme";
import "./index.css";
import "./dashboard-theme.css";
import "./design-system.css";
import "./ui/ui.css";
import "./portals/shared/portal-dark.css";
import "./modules/module-3/module-3-contrast.css";
import "./typography-floor.css";
import "./noir-theme.css";
import "./mobile-responsive.css";
import "./portal-scroll.css";
import "./portals/shared/portal-shell-fixes.css";
import "./noir-theme-final.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider>
      <App />
    </ThemeProvider>
  </StrictMode>,
);
