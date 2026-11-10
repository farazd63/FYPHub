export function readSidebarCollapsed(key: string): boolean {
  try {
    return window.localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
}

export function writeSidebarCollapsed(key: string, collapsed: boolean): void {
  try {
    window.localStorage.setItem(key, String(collapsed));
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
}
