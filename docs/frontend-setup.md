# Frontend Setup

The frontend uses React, Vite, TypeScript, and Tailwind CSS.

## Local API configuration

Copy `frontend/.env.example` to `frontend/.env` when an explicit local API origin is needed. `VITE_API_BASE_URL` is non-secret and defaults to `http://127.0.0.1:8010` if omitted. Do not place database credentials or other secrets in frontend environment files.

```powershell
cd frontend
npm.cmd run dev
```

## Shared-team registration

The Create Team Account screen loads academic cycles and the selected cycle's group policy from the API. It uses the fetched maximum (including the creator), preserves excess member rows if a smaller policy is selected, and prevents submission until the selected configuration and all fields are valid.

It sends `POST /api/v1/team-registration` with the creator separate from additional member contact records. Confirm password remains client-side. Backend error field paths are mapped to the relevant step and stable member row; password values are never stored or logged. A successful HTTP `201` shows a confirmation and clears both password fields.

The login screen uses `VITE_API_BASE_URL` and sends requests with browser cookie credentials. Run the API at the configured local origin (`http://127.0.0.1:8010`) and the Vite frontend at `http://127.0.0.1:5174`; the backend allows that exact credentialed origin. Login accepts a registered email or the creator registration number, not a team member contact email. Password recovery remains unavailable until an email delivery service is configured.

The backend permits only the exact local frontend origin `http://127.0.0.1:5174`, with no wildcard origin or credential support.

## Password-entry feedback

Password-creation fields in shared-team registration and Admin account creation use the same local UI helper. Once a user starts typing, it displays a checklist for length, uppercase, lowercase, number, and special-character recommendations, plus a Weak/Medium/Strong estimate. The score is the number of the five displayed criteria met: a password under eight characters is Weak; otherwise 1–2 is Weak, 3–4 is Medium, and all 5 is Strong. This is an estimate only, not a security guarantee.

The current account policy still requires only an unchanged 8–128-character password. Uppercase, lowercase, number, and special-character checks are advisory and never block submission. Confirmation fields report only match state; sign-in does not show creation recommendations or instructional password helper text. Password values remain local to the form and are sent unchanged in the existing requests.

After changing `.env`, restart the existing Vite development server. Restart the backend development server after backend CORS changes if it is not already running with reload.
