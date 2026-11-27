type CycleLike = {
  display_name?: string | null;
  name?: string | null;
  code?: string | null;
  academic_year?: number | string | null;
  session?: string | null;
};

const clean = (value: string | null | undefined) => value?.trim() || "";

const sessionLabel = (value: string | null | undefined) => {
  const session = clean(value).toUpperCase();
  if (session === "FALL") return "Fall";
  if (session === "SPRING") return "Spring";
  return clean(value);
};

/** Prefer the human-readable cycle name and use metadata only as a fallback. */
export function cycleLabel(cycle?: CycleLike | string | null): string {
  if (typeof cycle === "string") return clean(cycle) || "Academic cycle";
  if (!cycle) return "Academic cycle";
  const named = clean(cycle.display_name || cycle.name);
  if (named) return named;
  const year = cycle.academic_year == null ? "" : String(cycle.academic_year);
  const session = sessionLabel(cycle.session);
  return [session, year].filter(Boolean).join(" ") || clean(cycle.code) || "Academic cycle";
}

/**
 * Group names are generated as "Spring 2027 Group 6". When the cycle is
 * already shown in a nearby label, keep only the group-specific part so the
 * same cycle is not printed twice in one card or page.
 */
export function shortGroupLabel(groupName: string | null | undefined, cycle?: CycleLike | string | null): string {
  const name = clean(groupName);
  if (!name) return "Group";
  const cycleName = typeof cycle === "string" ? clean(cycle) : cycle ? cycleLabel(cycle) : "";
  if (!cycleName) return name;
  const escapedCycle = cycleName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const prefix = new RegExp(`^${escapedCycle}\\s*[-:]?\\s+`, "i");
  const shortened = name.replace(prefix, "").trim();
  return shortened || name;
}
