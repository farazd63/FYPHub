# Integration matrix

| Existing capability | Reused | Boundary |
|---|---|---|
| Cookie session auth and mutating Origin checks | `app.auth` | No authentication weakening |
| Supervisor request assignment | `SupervisorRequest` accepted relationship | Supervisor report access only |
| Existing audit history | `add_admin_audit_event` with allowlisted Module 03 keys | No raw document/session data |
| Existing portals and theme | Student/Admin portal shells and shared CSS patterns | No backend or Module 2 behavior changes |
| Existing PDF extraction | Kept for supervisor requests | Module 03 uses its own AST parser to avoid changing that workflow |
