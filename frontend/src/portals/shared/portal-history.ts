export type DashboardHistoryPage = "account" | "admin-portal";

function currentState() {
  return window.history.state && typeof window.history.state === "object"
    ? window.history.state as Record<string, unknown>
    : {};
}

export function pushPortalRoute(path: string, page: DashboardHistoryPage = "account") {
  window.history.pushState(
    { ...currentState(), fyphubNavigation: { page } },
    "",
    appPath(path),
  );
}

export function replacePortalRoute(path: string, page: DashboardHistoryPage = "account") {
  window.history.replaceState(
    { ...currentState(), fyphubNavigation: { page } },
    "",
    appPath(path),
  );
}
import { appPath } from "../../platform-path";
