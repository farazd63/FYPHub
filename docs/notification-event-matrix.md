# Cross-portal notification coverage

The header bell reads `module2_notifications` for the signed-in user. Business
mutations enqueue notification rows in the same database transaction as the
mutation, so a failed action cannot produce a false alert. Items stay unread
until the user clicks them.

| Event | Student portal | Supervisor portal | Admin portal |
| --- | --- | --- | --- |
| Supervisor request submitted/resubmitted | — | Selected supervisor | Active admins |
| Supervisor request accepted, rejected, or changes requested | Requesting group | — | Active admins |
| Supervisor-request conversation message | Other side of conversation | Other side of conversation | Active admins |
| Proposal PDF uploaded/replaced for a request | — | Selected supervisor | Active admins |
| Collaboration message or shared file | Other group participants | Assigned supervisor/group | Active admins |
| Required document published, updated, closed, archived, or reopened | Affected students | Assigned group supervisor | Active admins when applicable |
| Required document uploaded/resubmitted | — | Assigned supervisor | Active admins |
| Required document reviewed/commented | Affected students | Reviewer confirmation | Active admins |
| Group member added or group access approved/deactivated | Group account where access remains active | Assigned supervisor | Active admins |
| Group leadership transferred, member leaves, or group dissolved | Affected group | Assigned supervisor | Active admins |
| Supervisor assignment ended, unavailable, restored, reassigned, or replacement completed | Affected group | Previous/new supervisor | Active admins |
| Milestone, task, or supervision meeting changed | Affected group | Assigned supervisor | Active admins |
| Defense scheduled or rescheduled | Affected group | Assigned supervisor | Active admins and assigned evaluators |
| Evaluation saved, submitted, resolved, or sent for recheck | Affected group | Assigned supervisor | Active admins and assigned evaluators |

Notifications carry a deep-link path plus entity metadata (`team_id`, cycle,
request, document, assignment, or message IDs) so the header item opens the
relevant portal section rather than only showing a generic toast.
