import { useEffect, useState } from "react";

const STORAGE_PREFIX = "fyphub.sidebar.collapsed.";

const readCollapsed = (key: string) => {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(key) === "true";
  } catch {
    return false;
  }
};

export function usePersistentSidebarCollapse(scope: string) {
  const key = `${STORAGE_PREFIX}${scope}`;
  const [collapsed, setCollapsed] = useState(() => readCollapsed(key));

  useEffect(() => {
    try {
      window.localStorage.setItem(key, String(collapsed));
    } catch {
      // A blocked or unavailable storage should not prevent sidebar navigation.
    }
  }, [collapsed, key]);

  return [collapsed, setCollapsed] as const;
}
