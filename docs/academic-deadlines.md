# Academic Deadline Configuration

M1-G.1 provides ADMIN-only, non-operational deadline configuration. It records administrator-supplied values and creates no defaults or sample deadlines.

## Data and history

`AcademicDeadline` is a stable identity fixed to one existing `AcademicCycle`. `AcademicDeadlineVersion` stores numbered snapshots treated as immutable by the API containing the name, optional description, canonical UTC due instant, IANA timezone, creator, and timestamp. The database uniquely constrains each identity/version number. A new configuration change creates the next version; there is no update-in-place or delete API.

“Latest” means the newest recorded configuration only. It does not mean approved, published, active, or available to submission/reminder processing.

## Timezone contract

Python's `zoneinfo` uses system IANA timezone data or the separately installed `tzdata` package. No timezone dependency was added, so deployments must provide a timezone database. If it is unavailable, timezone-dependent endpoints return a sanitized HTTP 503 configuration error. This environment resolves `Asia/Karachi` and exposes 598 zones using installed `tzdata`. The client obtains supported IANA identifiers from the authenticated API and never assumes the browser or server timezone.

Preview requests provide:

- `local_due_at`: ISO local wall time without an embedded offset;
- `time_zone`: explicit IANA identifier;
- `utc_offset`: omitted when the local time has one valid offset, but required when it is ambiguous.

The server rejects invalid zones, nonexistent local times, and offsets that do not belong to the selected zone at that wall time. An ambiguous local time returns its valid offsets and must be resubmitted with the intended choice. The response contains an aware canonical UTC instant.

Create/version requests repeat the local time, zone, selected offset, and server-previewed `due_at_utc`. The canonical timestamp must exactly match a fresh server resolution. Both initial creation and subsequent-version creation reject naive timestamps with HTTP 422; the server timezone is never inferred. This prevents a stale or independently edited preview from being saved.

## API

All endpoints require an active account with persisted `ADMIN` role. POST requests apply the configured browser-Origin validation.

- `GET /api/v1/admin/time-zones`
- `POST /api/v1/admin/academic-deadlines/preview`
- `GET /api/v1/admin/academic-deadlines?academic_cycle_id={id}`
- `GET /api/v1/admin/academic-deadlines/{id}`
- `POST /api/v1/admin/academic-deadlines`
- `POST /api/v1/admin/academic-deadlines/{id}/versions`

Initial creation includes `academic_cycle_id`. Subsequent versions cannot move the stable identity to another cycle. Writes lock the cycle before the deadline allocator, allocate the next version inside the transaction, and commit the complete version and audit event together.

## Operational boundary

This checkpoint does not define submission stages, deadline defaults, approval/publication states, grace periods, extensions, penalties, late-submission handling, reminder recipients or cadence, delivery scheduling, escalation rules, or enforcement. Those require separate academic-policy decisions and later implementation.

## Reported verification evidence

- 8 focused deadline tests and 63 full backend tests passed, including naive-write rollback and missing-timezone-data regressions.
- Alembic current/head are `a2b3c4d5e6f7`; the schema check is clean.
- `pip check` passed. Frontend lint/build were previously reported as passed and were not rerun for this backend fix.
- Screenshot evidence confirms that server preview converted 20 October 2026, 17:00 in `Asia/Karachi` to 12:00 UTC.

Browser preview invalidation, save/version-history interactions, and mobile verification remain pending. Submission enforcement, reminders, escalation, and M1/P1 completion remain pending.
