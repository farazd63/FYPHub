# UI Design Decisions

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
