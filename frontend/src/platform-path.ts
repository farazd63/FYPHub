const configuredBase = (import.meta.env.BASE_URL || "/").replace(/\/+$/, "");

/** Return the application route without the repository prefix used by Pages. */
export function appPathname() {
  const pathname = window.location.pathname;
  if (!configuredBase || configuredBase === "/") return pathname;
  if (pathname === configuredBase) return "/";
  return pathname.startsWith(`${configuredBase}/`)
    ? pathname.slice(configuredBase.length) || "/"
    : pathname;
}

/** Prefix an application route for local root hosting or a Pages subpath. */
export function appPath(pathname: string) {
  const normalized = pathname.startsWith("/") ? pathname : `/${pathname}`;
  return configuredBase && configuredBase !== "/"
    ? `${configuredBase}${normalized === "/" ? "/" : normalized}`
    : normalized;
}
