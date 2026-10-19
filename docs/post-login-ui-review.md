# Post-login UI review

| Screen | Implemented controls | Verification | Remaining gaps |
| --- | --- | --- | --- |
| Overview | Real academic cycle and group-policy read view, including loading/empty/error/retry states | Source review and frontend build | Browser review pending. |
| Users & Roles | Search and role/status filters, fixed role badges, account creation, status controls | `test_admin_users.py` | Desktop/mobile browser review pending. |
| Academic Cycles & Policies | Cycle and group-policy management | Existing backend tests | Browser review pending. |
| Proposal Templates | Internal reference/version controls | Existing template tests | Publication and compliance work are not implemented. |

Assigned roles are fixed after account creation. The create-account role selector assigns the initial role; filters only filter; the legacy role-change endpoint returns `assigned_role_locked` without changing accounts, sessions, or audit records.
