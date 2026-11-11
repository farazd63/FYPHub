# Embedded Student Collaboration Channel

The Student Overview contains an embedded Collaboration Channel card below the existing group-members card. Header, sidebar entries, routes, authentication and existing dashboard components are unchanged.

## Existing APIs reused

- `GET /api/v1/student/group/me`: current group metadata.
- `GET /api/v1/student/collaboration/channels`: authorized active channels, filtered to the current group by the card.
- `GET /api/v1/student/collaboration/channels/{id}`: authorized channel metadata.
- `GET /api/v1/student/collaboration/channels/{id}/messages`: history. Optional `limit` (1–200) and `before_id` support loading earlier messages. Existing consumers without pagination retain the complete-history response.
- `POST /api/v1/student/collaboration/channels/{id}/messages`: send plain-text content.
- New `POST /api/v1/student/collaboration/channels/{id}/read`: monotonically advance the current principal's read marker using `{ "message_id": ... }`.
- Matching supervisor channel routes reuse the same authorization and handlers. Existing supervisor group-conversation endpoints continue to call these handlers.

## Authorization and persistence

An active channel, active assignment and accepted supervision request are required. Only the group's shared student principal, active group members, and the specific assigned supervisor pass channel authorization. Other groups, unrelated supervisors and other roles are denied. A dissolved group, ended assignment or archived channel immediately loses access.

The portal's shared group login and cookie-session authentication are preserved. Group members continue using their existing shared credentials; read markers and sender attribution are associated with the authenticated account, not an inferred individual behind shared credentials. Member-level authorization is also tested independently.

The existing `collaboration_channels`, `collaboration_messages` and `collaboration_participants` tables are reused. Migration `ri2d3e4f5a6b` adds nullable `last_read_message_id` and `last_read_at` columns to participants; no duplicate chat tables are introduced. A read marker may reference only a non-deleted message from that channel and cannot move backwards.

Messages must contain non-whitespace content and be at most 4,000 characters. Content is stored without trimming so indentation, line breaks and trailing newlines survive. The browser renders messages as escaped React text with pre-wrap and long-word wrapping, never executable HTML.

## UI behavior

The card displays group name, academic cycle, active members, assigned supervisor and assignment status. Before acceptance it shows exactly: “Collaboration channel will be available after a supervisor accepts your request.”

Messages refresh every five seconds while the card is open and the document is visible; channel metadata refreshes every ten seconds. Send refreshes the history immediately and retains the draft on failure. Enter sends; Shift+Enter inserts a line break; IME composition does not send. New messages scroll to the bottom only when the user is already following the conversation. Read markers are saved only while the visible history is at the latest messages. Older messages can be loaded without jumping to the newest message.

## Validation performed

- Authenticated HTTP tests: shared group account access, assigned supervisor access, other-group/supervisor/admin rejection, pre-acceptance rejection, ended-assignment rejection, message creation, exact multiline content preservation, empty/overlong/spoofed message validation, read-marker isolation and monotonicity, pagination, and compatibility with the existing supervisor conversation API.
- Membership authorization tests for individual member identities and removed members.
- Frontend helper tests for Enter/Shift+Enter/IME handling, message validation, chronological merging and deduplication.
- Scoped ESLint and production TypeScript/Vite build.

Tests use rollback-isolated database fixtures and do not submit messages to real groups.
