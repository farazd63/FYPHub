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
    path,
  );
}

export function replacePortalRoute(path: string, page: DashboardHistoryPage = "account") {
  window.history.replaceState(
    { ...currentState(), fyphubNavigation: { page } },
    "",
    path,
  );
}
