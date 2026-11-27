type CycleLike = {
  id?: number | string | null;
  display_name?: string | null;
  name?: string | null;
  code?: string | null;
  label?: string | null;
  academic_year?: number | string | null;
  year?: number | string | null;
  session?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

const clean = (value: string | null | undefined) => value?.trim() || "";

const sessionLabel = (value: string | null | undefined) => {
  const session = clean(value).toUpperCase();
  if (session === "FALL") return "Fall";
  if (session === "SPRING") return "Spring";
  return clean(value);
};

const cycleText = (cycle: CycleLike) =>
  [cycle.display_name, cycle.name, cycle.code, cycle.label]
    .map((value) => clean(value))
    .filter(Boolean)
    .join(" ");

const cycleYear = (cycle: CycleLike) => {
  const explicit = Number(cycle.academic_year ?? cycle.year);
  if (Number.isFinite(explicit)) return explicit;
  const matches = cycleText(cycle).match(/\b(?:19|20|21)\d{2}\b/g);
  return matches?.length ? Number(matches[matches.length - 1]) : Number.NEGATIVE_INFINITY;
};

const cycleSessionRank = (cycle: CycleLike) => {
  const value = clean(cycle.session).toUpperCase() || cycleText(cycle).toUpperCase();
  if (value.includes("FALL") || value.includes("AUTUMN")) return 2;
  if (value.includes("SPRING")) return 1;
  return 0;
};

const numericValue = (value: number | string | null | undefined) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
};

const timestampValue = (value: string | null | undefined) => {
  if (!value) return Number.NEGATIVE_INFINITY;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : Number.NEGATIVE_INFINITY;
};

const compareDescending = (left: number, right: number) =>
  left === right ? 0 : left > right ? -1 : 1;

/** Compare academic cycles chronologically, newest cycle first. */
export function compareCyclesDesc(left: CycleLike, right: CycleLike): number {
  return (
    compareDescending(cycleYear(left), cycleYear(right)) ||
    compareDescending(cycleSessionRank(left), cycleSessionRank(right)) ||
    compareDescending(timestampValue(left.created_at), timestampValue(right.created_at)) ||
    compareDescending(timestampValue(left.updated_at), timestampValue(right.updated_at)) ||
    compareDescending(numericValue(left.id), numericValue(right.id))
  );
}

export function sortCyclesDesc<T extends CycleLike>(cycles: readonly T[]): T[] {
  return [...cycles].sort(compareCyclesDesc);
}

type GroupLike = {
  id?: number | string | null;
  group_number?: number | string | null;
  group_name?: string | null;
  name?: string | null;
  group_code?: string | null;
  label?: string | null;
  academic_cycle_id?: number | string | null;
  academic_cycle?: CycleLike | string | null;
  academic_cycle_name?: string | null;
  cycle_name?: string | null;
  academic_year?: number | string | null;
  session?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_activity_at?: string | null;
  last_submission_at?: string | null;
  project?: { updated_at?: string | null } | null;
  assignment?: { assigned_at?: string | null } | null;
  supervisor_assignment?: { assigned_at?: string | null } | null;
};

/** Return a cycle-scoped group label without ever falling back to a database ID. */
export function groupDisplayLabel(
  group?: GroupLike | null,
  cycle?: CycleLike | string | null,
  fallbackNumber?: number | string | null,
): string {
  const number = numericValue(group?.group_number);
  if (Number.isFinite(number) && number > 0) return `Group ${number}`;

  const raw = clean(group?.group_name || group?.name || group?.label);
  const shortened = shortGroupLabel(raw, cycle);
  if (
    /^(?:(?:spring|fall)\s+\d{4}\s+)?(?:group|team)\s+\d+$/i.test(raw) ||
    /^(?:group|team)\s+\d+$/i.test(shortened) ||
    /^\d+$/.test(shortened)
  ) {
    const fallback = numericValue(fallbackNumber);
    return Number.isFinite(fallback) && fallback > 0 ? `Group ${fallback}` : "Group";
  }
  return shortened || "Group";
}

const groupCycle = (group: GroupLike): CycleLike => {
  if (group.academic_cycle && typeof group.academic_cycle === "object") {
    return group.academic_cycle;
  }
  return {
    id: group.academic_cycle_id,
    display_name:
      (typeof group.academic_cycle === "string" ? group.academic_cycle : null) ||
      group.academic_cycle_name ||
      group.cycle_name ||
      group.label,
    academic_year: group.academic_year,
    session: group.session,
  };
};

const groupActivity = (group: GroupLike) =>
  Math.max(
    timestampValue(group.last_activity_at),
    timestampValue(group.last_submission_at),
    timestampValue(group.updated_at),
    timestampValue(group.created_at),
    timestampValue(group.project?.updated_at),
    timestampValue(group.supervisor_assignment?.assigned_at),
    timestampValue(group.assignment?.assigned_at),
  );

/** Sort groups by newest cycle, then latest activity/assignment, then group number. */
export function sortGroupsDesc<T extends GroupLike>(groups: readonly T[]): T[] {
  return [...groups].sort((left, right) =>
    compareCyclesDesc(groupCycle(left), groupCycle(right)) ||
    compareDescending(groupActivity(left), groupActivity(right)) ||
    compareDescending(numericValue(left.group_number), numericValue(right.group_number)) ||
    compareDescending(numericValue(left.id), numericValue(right.id)),
  );
}

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
