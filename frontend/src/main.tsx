import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import "./dashboard-theme.css";
import "./design-system.css";
import "./portals/shared/portal-dark.css";
createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
