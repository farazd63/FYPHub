# UI Design Decisions

## Admin colour system

Implemented Admin screens use scoped primary `#4663FF`, hover `#354FE0`, selected `#EEF1FF`, text `#183047`, muted text `#607087`, page `#F4F6FB`, white surfaces, and `#DCE3ED` borders. Semantic success, error, and warning colours remain distinct. Public-auth styling is not affected. Browser visual verification remains pending.

## Shared application theme

The application-level theme tokens are the authority for public authentication and implemented post-login screens: primary `#4663FF`, hover `#354FE0`, selected `#EEF1FF`, text `#243746`, muted `#607087`, page `#F4F6FB`, solid surface `#FFFFFF`, and border `#DCE3ED`. Future Student, Supervisor, Coordinator, Panel, and Admin screens must reuse these tokens. Semantic success, error, and warning colours remain exceptions rather than separate themes.

## F1: Create Team Account

The F1 registration screen is labelled **Create Team Account**. It is a visual-only mockup and has no submission, API, or database behavior.

### Shared team account model

- Each team has one designated login email and one shared password.
- All team members use those same credentials.
- Member university emails are contact records only; they are not login identifiers.
- The screen does not represent invitations, individual member accounts, or login through a member’s university/contact email.
- The account creator is also a team member and counts toward the configured group-size limit.
- The maximum group size is intentionally not hardcoded. The future integrated flow will follow the configured limit.

### Planned form contents

The future Create Team Account flow will collect:

- account creator name, registration number, and university email;
- designated shared login email and password; and
- each member’s name, registration number, and university email.

### Visual direction

The mockup preserves the agreed simple, professional presentation using a cream base, teal actions and accents, sage supporting panels, and navy type. The call to action is deliberately disabled while this remains a visual-only checkpoint; that implementation status is documented here rather than explained on the user screen.

### Current scope

The existing student-registration API creates an individual `STUDENT` record only. It does not support group creation, shared credentials, members, or contact records. The visual mockup makes no claim that this backend capability already exists.

## Frontend correction

The visual mockup is now a responsive React, Vite, TypeScript, and Tailwind CSS screen with a centered form card, original logo, stable member rows, local validation, and show/hide password controls. It remains frontend work awaiting backend integration and does not submit or create accounts.

The Sign Up flow now presents Account Details, Login Details, and Team Members one step at a time with Back/Next navigation. Sign In remains display-only pending authentication integration.

## Role-based account interface

- Login now has the FYPHub brand, four accessible role cards (Student, Supervisor, Evaluator, Coordinator), registered email/creator ID, show/hide password, recovery link, loading/error states, and a Create Account link.
- Login sends the selected role and either the registered login email or creator registration number to the backend with cookie credentials. It restores a real session via `/api/v1/auth/me` and provides an authenticated account view plus logout until real dashboards exist.
- Signup starts with matching role cards. Student continues into the existing shared-team multistep registration unchanged. Staff, evaluator, and coordinator registrations show a restricted invitation/approval message rather than collecting unsupported public credentials.
- The configured session policy is eight hours (documented in `docs/authentication.md`). There is intentionally no “Remember Me” checkbox because no alternate persistence lifetime has been approved.
- Public authentication navigation uses browser history identifiers only: Sign In, signup role selection, and each shared-team registration step can be revisited with Back/Forward while the mounted form retains its values. Returning or moving forward to a later registration step revalidates earlier steps and falls back to the earliest invalid step. Passwords and personal form values are never placed in URLs, `history.state`, or browser storage.
- Password creation feedback shows only currently missing suggestions alongside the local strength estimate. Suggestions disappear as criteria are satisfied and return if the criterion is no longer met; character-category suggestions remain advisory rather than submission requirements.
- All public authentication screens use `AuthLayout`: the local student-collaboration photograph becomes the full background under a navy contrast overlay, with original FYPHub branding and approved product-purpose copy on desktop left and a frosted translucent form surface on the right. This covers Sign In, signup role selection, restricted registration, recovery information, registration confirmation, and every shared-team registration step. On narrow screens the left copy is hidden, branding remains first in the card, and the form scrolls naturally. The glass surface has a more opaque non-blur fallback. Its image is `frontend/src/assets/sign-in-students.webp`, downloaded from [Pexels: “Students Studying Together while Looking at the Screen of a Laptop” by Yan Krukau](https://www.pexels.com/photo/students-studying-together-while-looking-at-the-screen-of-a-laptop-8199761/) and used under the [Pexels License](https://www.pexels.com/license/). Role selection uses compact horizontal cards, with Administrator spanning the final row; selected states and primary authentication actions use royal blue.

Every future frontend change must consider desktop, tablet, and mobile responsiveness. Documentation for each change must record whether those viewports received actual browser verification or remain manually pending.

### Registration progress indicator

The compact three-step form uses a numbered progress indicator for Account Details, Login Details, and Team Members. Completed steps use checkmarks; the connecting CSS progress line transitions as the user moves forward or back. Back is hidden on Step 1 so Next remains aligned to the right. Shared-team registration and Sign In remain disabled pending backend integration. Password-strength feedback is also pending.

## Administrator portal layout

The M1-A Administrator portal now uses a compact academic-administration layout: cream canvas, deep-teal actions, sage active state, navy text, a 240px desktop sidebar, and a keyboard-accessible mobile menu. The header retains the logo, Administrator badge, authenticated user, and Logout without repeating a dominant account card. Overview presents the existing academic-cycle and group-policy data in a responsive table-like list with honest loading, empty, missing-policy, and failure states. Future M1 entries remain semantic disabled labels.

The implementation adds a 300ms page opacity/8px transform entrance, an Academic Cycles entrance delayed by 80ms, a 250ms mobile menu/overlay transition, and 150–200ms button feedback. The Academic Cycles entrance is attached to its stable section, so API state updates do not replay it. The global reduced-motion rule removes these transitions for users who request it. This redesign is implemented but awaits user visual approval; no screenshots or browser review are claimed here.

## Shared role-portal standard

The Administrator portal is the current visual and interaction baseline for future Student, Supervisor, Coordinator, and Panel Member portals. It does not make their information architecture identical and remains subject to user visual approval.

- Use the same full-width responsive shell: compact branded header, authenticated user identity, Logout, 240px desktop sidebar, accessible mobile menu, cream canvas, navy text, teal actions, sage active state, subtle borders, and restrained shadows.
- Use the same accessible primitives for navigation, forms, feedback states, cards, tables, buttons, focus treatment, and responsive padding. Reuse shared portal components where their behavior is genuinely shared.
- Give each role only proposal-defined navigation and content backed by authorized APIs. Role permissions are enforced by the backend; a visually shared component never implies a shared privilege.
- Render unimplemented areas as clearly disabled labels or omit them. Do not create empty dashboards, dummy records, statistics, charts, notifications, or inactive controls that look operational.
- Preserve real loading, empty, error, and success states, and use credentialed requests for authenticated data.

| Role | Future portal focus | Current portal state |
| --- | --- | --- |
| Administrator | Academic management and M1 administration | Partial: M1-A shell and real cycle overview only |
| Student | Team/collaboration and proposal lifecycle | Not implemented |
| Supervisor | Supervision and allocation responsibilities | Not implemented |
| Coordinator | Programme/cycle coordination responsibilities | Not implemented |
| Panel Member | Evaluation responsibilities | Not implemented |
