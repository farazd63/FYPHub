const configuredBase = (import.meta.env.BASE_URL || "/").replace(/\/+$/, "");

/** Return the application route without the configured asset base prefix. */
export function appPathname() {
  const pathname = window.location.pathname;
  if (!configuredBase || configuredBase === "/") return pathname;
  if (pathname === configuredBase) return "/";
  return pathname.startsWith(`${configuredBase}/`)
    ? pathname.slice(configuredBase.length) || "/"
    : pathname;
}

/** Prefix an application route for the configured frontend base path. */
export function appPath(pathname: string) {
  const normalized = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return configuredBase && configuredBase !== "/"
    ? `${configuredBase}${normalized === "/" ? "/" : normalized}`
    : normalized;
}
