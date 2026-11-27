import { useEffect, useId, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AdminPortal } from "./AdminPortal";
import { PasswordField } from "./PasswordField";
import { passwordPolicyError } from "./passwordPolicy";
import {
  emailValidationMessage,
  normalizeEmail,
  szabistEmailValidationMessage,
} from "./emailValidation";
import { StudentPortal } from "./portals/student/StudentPortal";
import { SupervisorPortal } from "./portals/supervisor/SupervisorPortal";
import { CoordinatorPortal } from "./portals/coordinator/CoordinatorPortal";
import { StudentEvaluatorPortal as EvaluatorPortal } from "./portals/student/modules/StudentEvaluatorPortal";
import authHeroImage from "./assets/fyphub-auth-campus.png";
import { ThemeToggle } from "./ui/ThemeToggle";
import { Stepper } from "./ui/Stepper";
import { Button } from "./ui/Button";
import { Card } from "./ui/Card";
import { WelcomeLanding } from "./pages/WelcomeLanding";
import { sortCyclesDesc } from "./lib/displayLabels";
import { appPath, appPathname } from "./platform-path";
import "./auth.css";

type Member = { id: string; full_name: string; email: string; registration: string };
type Cycle = {
  id: number;
  code: string;
  display_name: string;
  academic_year?: number | null;
  session?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  registration_open: boolean;
};
type Policy = { min_group_size: number; max_group_size: number };
type FieldErrors = Record<string, string>;
type ApiDetail = {
  code?: string;
  message?: string;
  field?: string;
  fields?: { path: string; code?: string }[];
};
type PublicRole = "STUDENT" | "SUPERVISOR" | "PANEL_MEMBER" | "COORDINATOR";
type LoginRole = PublicRole | "ADMIN";
type SafeUser = {
  id: number;
  full_name: string;
  email: string;
  registration_number: string | null;
  role: string;
  is_active: boolean;
  group_id?: number | null;
  group_email?: string | null;
  principal_type?: "GROUP" | "ACCOUNT";
  group_name?: string | null;
  academic_cycle?: string | null;
  group_status?: string | null;
  members?: Array<{
    id: number;
    full_name: string;
    registration_number: string;
    email: string | null;
    designation?: string;
    is_active?: boolean;
  }>;
};
type PasswordResetDeliveryStatus = {
  development_mode: boolean;
  smtp_configured: boolean;
};
type DevelopmentResetLinkState = "idle" | "loading" | "ready" | "missing" | "error";
type PublicPage = "welcome" | "in" | "up" | "recover";
type StudentSignupMode = "group";
type PublicRoute = { page: PublicPage; signupRole: LoginRole | null; step: 1 | 2 | 3; studentMode: StudentSignupMode | null };
type DashboardPage = "account" | "admin-portal";

const STEPS = ["Academic Cycle", "Group Members", "Group Credentials"];
const SIGNUP_STEP_IDS = ["cycle", "members", "credentials"] as const;
const AUTH_SWITCH_DURATION = 760;
const MODAL_FOCUSABLE = 'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

function useModalFocusManager() {
  const activeDialog = useRef<HTMLElement | null>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const getDialog = () => {
      const dialogs = Array.from(document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'));
      return dialogs[dialogs.length - 1] ?? null;
    };
    const focusFirst = (dialog: HTMLElement) => {
      const target = dialog.querySelector<HTMLElement>(`[autofocus], ${MODAL_FOCUSABLE}`) ?? dialog;
      if (target === dialog && !dialog.hasAttribute("tabindex")) dialog.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
    };
    const sync = () => {
      const nextDialog = getDialog();
      if (nextDialog === activeDialog.current) return;
      if (nextDialog) {
        if (!activeDialog.current) {
          const current = document.activeElement;
          restoreFocus.current = current instanceof HTMLElement ? current : null;
        }
        activeDialog.current = nextDialog;
        document.body.classList.add("fy-modal-open");
        window.requestAnimationFrame(() => {
          if (activeDialog.current === nextDialog && !nextDialog.contains(document.activeElement)) focusFirst(nextDialog);
        });
        return;
      }
      activeDialog.current = null;
      document.body.classList.remove("fy-modal-open");
      const previous = restoreFocus.current;
      restoreFocus.current = null;
      if (previous?.isConnected) window.requestAnimationFrame(() => previous.focus({ preventScroll: true }));
    };
    const onFocusIn = (event: FocusEvent) => {
      const dialog = activeDialog.current ?? getDialog();
      if (dialog && event.target instanceof Node && !dialog.contains(event.target)) {
        event.stopPropagation();
        focusFirst(dialog);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Tab") return;
      const dialog = activeDialog.current ?? getDialog();
      if (!dialog) return;
      const nodes = Array.from(dialog.querySelectorAll<HTMLElement>(MODAL_FOCUSABLE));
      if (!nodes.length) {
        event.preventDefault();
        focusFirst(dialog);
        return;
      }
      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      if (!dialog.contains(document.activeElement)) {
        event.preventDefault();
        first.focus();
      } else if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("focusin", onFocusIn, true);
    document.addEventListener("keydown", onKeyDown, true);
    sync();
    return () => {
      observer.disconnect();
      document.removeEventListener("focusin", onFocusIn, true);
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.classList.remove("fy-modal-open");
    };
  }, []);
}

const createClientId = () => {
  const browserCrypto = globalThis.crypto;
  if (typeof browserCrypto?.randomUUID === "function") return browserCrypto.randomUUID();
  if (typeof browserCrypto?.getRandomValues === "function") {
    const bytes = new Uint8Array(16);
    browserCrypto.getRandomValues(bytes);
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
};
const isLandingPath = (pathname: string) => pathname === "/" || pathname === "/welcome";
const welcomePublicPath = () => (appPathname() === "/welcome" ? "/welcome" : "/");
const formatCycleLabel = (cycle: Cycle) => {
  const named = cycle.display_name?.trim();
  const base = named
    || (cycle.session && cycle.academic_year
      ? `${cycle.session === "FALL" || cycle.session === "Fall" ? "Fall" : cycle.session === "SPRING" || cycle.session === "Spring" ? "Spring" : cycle.session} ${cycle.academic_year}`
      : cycle.session?.trim() || (cycle.academic_year ? String(cycle.academic_year) : `Cycle #${cycle.id}`));
  return base;
};
const configuredApi = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
// Production is served with an nginx /api proxy. Keeping the API same-origin
// makes every portal work from localhost, a LAN hostname, or a reverse proxy,
// while preserving the cookie-backed session.
const browserOrigin = typeof window !== "undefined" ? window.location.origin : "";
const isLocalBackendUrl = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/i.test(configuredApi);
export const API = !configuredApi || isLocalBackendUrl ? browserOrigin : configuredApi;
const INPUT =
  "w-full rounded-lg border border-fy-border bg-fy-page px-3.5 py-3 text-base text-fy-text transition-colors focus:border-fy-brand disabled:cursor-not-allowed disabled:bg-fy-surface-muted disabled:opacity-70";
const PRIMARY =
  "fy-btn fy-btn--primary rounded-lg bg-fy-brand px-5 py-2.5 text-sm font-semibold text-fy-text-on-brand transition-colors hover:bg-fy-brand-hover disabled:cursor-not-allowed";
const AUTH_PRIMARY =
  "auth-primary fy-btn fy-btn--primary rounded-xl bg-fy-brand px-5 py-2.5 text-sm font-semibold text-fy-text-on-brand transition-colors hover:bg-fy-brand-hover disabled:cursor-not-allowed";
const PASSWORD_RESET_GENERIC_MESSAGE = "If an account exists for that email, a reset link will be sent.";
const FIRST_ADMIN_SETUP_PATH = "/setup/first-admin";
const academicCycleError = (status: number) => ({ 401: "Your session has expired. Please sign in again.", 403: "You are not authorized to load academic cycles.", 404: "The academic-cycles endpoint was not found.", 500: "The backend could not load academic cycles." }[status] ?? "Academic cycles could not be loaded.");
const fetchFirstAdminSetupAvailable = async (api: string) => {
  const response = await fetch(`${api}/api/v1/setup/first-admin/status`, { credentials: "include" });
  if (!response.ok) return false;
  const body = await response.json() as { available?: boolean };
  return body.available === true;
};

const newMember = (): Member => ({
  id: createClientId(),
  full_name: "",
  email: "",
  registration: "",
});
const registration = (value: string) => value.trim();
const sanitizeMemberValue = (field: keyof Omit<Member, "id">, value: string) => {
  if (field === "full_name") return value.replace(/[^\p{L} ]/gu, "").replace(/ {2,}/g, " ");
  if (field === "registration") return value.replace(/[^0-9]/g, "");
  return value;
};
const memberKey = (id: string, field: keyof Omit<Member, "id">) => `member.${id}.${field}`;
const validationFieldLabel = (key: string, members: Member[]) => {
  if (key === "account.cycle") return "Academic Cycle";
  if (key === "members.configuration") return "Group Members — member count";
  if (key === "login.email") return "Group Credentials — Email";
  if (key === "login.password") return "Group Credentials — Password";
  if (key === "login.confirm") return "Group Credentials — Confirm password";
  const match = key.match(/^member\.([^.]+)\.(full_name|email|registration)$/);
  if (!match) return "the highlighted field";
  const memberIndex = members.findIndex((member) => member.id === match[1]);
  const label = { full_name: "Full name", email: "Member email", registration: "Registration number" }[match[2]];
  return memberIndex >= 0 ? `Member ${memberIndex + 1} — ${label}` : `Group Members — ${label}`;
};
const validationNotice = (fieldErrors: FieldErrors, members: Member[]) => {
  const labels = [...new Set(Object.keys(fieldErrors).map((key) => validationFieldLabel(key, members)))];
  if (!labels.length) return "Please correct the highlighted fields.";
  return labels.length === 1
    ? `Please correct ${labels[0]}.`
    : `Please correct these fields: ${labels.join("; ")}.`;
};
const apiFieldErrorMessage = (key: string, fallback?: string, code?: string) => {
  if (fallback && fallback !== "Request validation failed.") return fallback;
  if (code === "missing" || code?.includes("empty")) return "This field is required.";
  if (key.endsWith(".email") || key === "login.email") return "Enter a valid email address.";
  if (key.endsWith(".registration")) return "Enter a registration number.";
  if (key.endsWith(".full_name")) return "Enter the member's full name.";
  return fallback ?? "Check this field.";
};
export const dashboardPageForRole = (role: unknown): DashboardPage | null => {
  if (role === "ADMIN") return "admin-portal";
  if (role === "STUDENT" || role === "SUPERVISOR" || role === "PANEL_MEMBER" || role === "COORDINATOR") return "account";
  return null;
};
const isDashboardPage = (value: unknown): value is DashboardPage => value === "account" || value === "admin-portal";
const publicRoute = (page: PublicPage, signupRole: LoginRole | null = null, step: 1 | 2 | 3 = 1, studentMode: StudentSignupMode | null = null): PublicRoute => {
  void signupRole;
  void studentMode;
  return { page, signupRole: page === "up" ? "STUDENT" : null, step: page === "up" ? step : 1, studentMode: page === "up" ? "group" : null };
};
const readPublicRoute = (value: unknown): PublicRoute | null => {
  const route = (value as { fyphubNavigation?: unknown } | null)?.fyphubNavigation as Partial<PublicRoute> | undefined;
  if (
    !route
    || (route.page !== "welcome" && route.page !== "in" && route.page !== "up" && route.page !== "recover")
    || (route.step !== 1 && route.step !== 2 && route.step !== 3)
  ) return null;
  return publicRoute(route.page, "STUDENT", route.step, "group");
};

function Logo({ compact = false, auth = false, authMobile = false }: { compact?: boolean; auth?: boolean; authMobile?: boolean }) {
  const classes = compact
    ? { wrapper: "fy-logo fy-logo--compact", icon: "fy-logo__icon", wordmark: "fy-logo__wordmark" }
    : auth
      ? { wrapper: "fy-logo fy-logo--auth", icon: "fy-logo__icon", wordmark: "fy-logo__wordmark" }
      : authMobile
        ? { wrapper: "fy-logo fy-logo--auth-mobile", icon: "fy-logo__icon", wordmark: "fy-logo__wordmark" }
        : { wrapper: "fy-logo", icon: "fy-logo__icon", wordmark: "fy-logo__wordmark" };
  return (
    <div className={classes.wrapper}>
      <svg aria-hidden="true" className={classes.icon} viewBox="0 0 56 40" fill="none">
        <path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor" />
        <path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <circle cx="49" cy="30" r="3" fill="currentColor" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span className={classes.wordmark}>FYPHub</span>
    </div>
  );
}

type AuthMode = "signin" | "signup";

function AuthLayout({ children, actions, compact = false, authMode, transitioning = false }: { children: ReactNode; actions?: ReactNode; compact?: boolean; authMode?: AuthMode; transitioning?: boolean }) {
  const activeFormRef = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!authMode) return;
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const timer = window.setTimeout(() => {
      const target = activeFormRef.current?.querySelector<HTMLElement>(".auth-form-view.is-active input:not([disabled]), .auth-form-view.is-active select:not([disabled]), .auth-form-view.is-active textarea:not([disabled]), .auth-form-view.is-active button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), button:not([disabled])");
      if (target) target.focus({ preventScroll: true });
      else activeFormRef.current?.focus({ preventScroll: true });
    }, reducedMotion || !transitioning ? 0 : AUTH_SWITCH_DURATION);
    return () => window.clearTimeout(timer);
  }, [authMode, transitioning]);
  const isSwitching = Boolean(authMode);
  return (
    <main className={`auth-stage ${compact ? "auth-stage--compact" : ""} ${isSwitching ? `auth-stage--switch ${authMode === "signup" ? "is-signup" : "is-signin"} ${transitioning ? "is-transitioning" : ""}` : ""}`}>
      <div className="auth-stage__glow auth-stage__glow--a" aria-hidden="true" />
      <div className="auth-stage__glow auth-stage__glow--b" aria-hidden="true" />
      <div className="auth-stage__noise" aria-hidden="true" />
      <div className={`auth-stage__panel auth-card auth-card-shell ${isSwitching ? (authMode === "signup" ? "is-signup" : "is-signin") : ""} ${transitioning ? "is-transitioning" : ""}`}>
        <div className="auth-stage__theme-dock" data-corner="top-right">
          <ThemeToggle />
        </div>
        <div className={`auth-stage__grid ${isSwitching ? "auth-stage__grid--switch" : ""}`}>
          {isSwitching && (
            <div className="auth-sweep" aria-hidden="true">
              <div className="auth-sweep-inner">
                <span className="auth-divider-edge" />
              </div>
            </div>
          )}
          <section className={`auth-stage__brand ${isSwitching ? "auth-welcome-panel" : ""}`}>
            <div className="auth-stage__media" aria-hidden="true">
              <img src={authHeroImage} alt="" width="1600" height="900" />
            </div>
            <div className="auth-stage__veil" aria-hidden="true" />
            <div className="auth-stage__orb auth-stage__orb--a" aria-hidden="true" />
            <div className="auth-stage__orb auth-stage__orb--b" aria-hidden="true" />
            <div className="auth-stage__orb auth-stage__orb--c" aria-hidden="true" />
            <svg className="auth-stage__line-art" viewBox="0 0 420 320" aria-hidden="true">
              <circle cx="310" cy="70" r="54" fill="none" stroke="currentColor" strokeWidth="1.25" opacity="0.35" />
              <circle cx="310" cy="70" r="28" fill="none" stroke="currentColor" strokeWidth="1.25" opacity="0.5" />
              <path
                d="M36 248c48-78 132-118 212-98 54 14 96 58 118 110M52 184c36-44 96-66 154-58M300 56c28 36 42 82 34 128"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
              />
              <path
                d="M88 96h48l24 40H112l24 72H76l16-48H52"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinejoin="round"
              />
            </svg>
            <div className="auth-stage__brand-copy">
              <div className="auth-stage__reveal auth-stage__reveal--1"><Logo auth /></div>
              <p className="auth-stage__eyebrow auth-stage__reveal auth-stage__reveal--2">Final year project workspace</p>
              <h1 className="auth-stage__reveal auth-stage__reveal--3">From your first idea to your final defense.</h1>
              <p className="auth-stage__lead auth-stage__reveal auth-stage__reveal--4">
                One calm place for proposals, milestones, feedback, and the day you present.
              </p>
            </div>
            <div className="auth-stage__credits" aria-label="FYPHub development team">
              <span className="auth-stage__credits-label">Designed &amp; developed by</span>
              <div className="auth-stage__credits-names">
                <span className="auth-stage__credits-name">Danish Faraz</span>
                <span className="auth-stage__credits-name">Muhammad Maaz</span>
                <span className="auth-stage__credits-name">Zain Ali Kiani</span>
              </div>
            </div>
          </section>
          <section ref={activeFormRef} tabIndex={-1} className={`auth-card auth-form-panel ${compact ? "auth-card--compact" : ""} ${authMode === "signup" ? "auth-form-panel--signup" : authMode === "signin" ? "auth-form-panel--signin" : ""}`}>
            <div className="auth-card__shine" aria-hidden="true" />
            <header className={`auth-card__header ${actions ? "auth-card__header--actions" : ""}`}>
              <div className="auth-card__mobile-brand"><Logo authMobile /></div>
              {actions ? <div className="auth-card__actions auth-card__actions--tools">{actions}</div> : null}
            </header>
            <div className="auth-card__body">{children}</div>
          </section>
        </div>
      </div>
    </main>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  inputMode,
  pattern,
  maxLength,
  autoComplete,
  disabled,
  error,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email" | "password";
  inputMode?: "text" | "numeric";
  pattern?: string;
  maxLength?: number;
  autoComplete?: string;
  disabled?: boolean;
  error?: string;
  required?: boolean;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
        {required && <span className="auth-field__required" aria-hidden="true"> *</span>}
      </label>
      <input
        id={id}
        type={type}
        inputMode={inputMode}
        pattern={pattern}
        maxLength={maxLength}
        value={value}
        autoComplete={autoComplete}
        disabled={disabled}
        required={required}
        aria-required={required}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        className={`${INPUT} ${error ? "border-[#a43a33]" : ""}`}
        onChange={(event) => onChange(event.target.value)}
      />
      {error && (
        <p id={errorId} role="alert" className="auth-field__error text-sm text-[#a43a33]">
          {error}
        </p>
      )}
    </div>
  );
}

type FirstAdminSetupProps = { api: string; onComplete: (email: string) => void; onBack: () => void };

function FirstAdminSetup({ api, onComplete, onBack }: FirstAdminSetupProps) {
  const [available, setAvailable] = useState<boolean | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({ setupKey: "", fullName: "", email: "", password: "", confirmPassword: "" });
  const emailError = form.email ? szabistEmailValidationMessage(form.email) ?? "" : "";

  useEffect(() => {
    let active = true;
    void fetchFirstAdminSetupAvailable(api)
      .then((isAvailable) => {
        if (active) setAvailable(isAvailable);
      })
      .catch(() => {
        if (active) setAvailable(false);
      });
    return () => { active = false; };
  }, [api]);

  const update = (field: keyof typeof form, value: string) => {
    setForm((current) => ({ ...current, [field]: value }));
    setError("");
    setMessage("");
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    if (!form.setupKey.trim() || !form.fullName.trim() || !form.email.trim() || !form.password || !form.confirmPassword) {
      setError("Complete all fields to create the first administrator.");
      return;
    }
    if (emailError) {
      setError(emailError);
      return;
    }
    const passwordError = passwordPolicyError(form.password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      const response = await fetch(`${api}/api/v1/setup/first-admin`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          setup_key: form.setupKey,
          full_name: form.fullName,
          email: normalizeEmail(form.email),
          password: form.password,
          confirm_password: form.confirmPassword,
        }),
      });
      const body = await response.json().catch(() => ({})) as { detail?: ApiDetail | string };
      if (!response.ok) {
        const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
        throw new Error(detail || "The first administrator could not be created.");
      }
      setMessage("Administrator account created. Redirecting to login...");
      window.setTimeout(() => onComplete(normalizeEmail(form.email)), 500);
    } catch (submissionError) {
      setError(submissionError instanceof Error ? submissionError.message : "The first administrator could not be created.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout compact>
      <div className="space-y-4">
        <h1 className="text-[26px] font-bold sm:text-[28px]">First Administrator Setup</h1>
        <p className="text-sm text-[#4f6470]">Create the first FYPHub administrator from this browser. This page closes permanently after the first administrator is created.</p>
        {available === null && <p role="status" className="rounded-lg bg-[#eaf2ff] px-3 py-2 text-sm text-[#243746]">Checking setup availability...</p>}
        {available === false && <><p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">First administrator setup is unavailable. It may already be completed or has not been enabled by the deployment operator.</p><button type="button" onClick={onBack} className={`${AUTH_PRIMARY} w-full`}>Back to Login</button></>}
        {available === true && <form onSubmit={(event) => void submit(event)} className="space-y-3">
          <Field label="One-time setup key" type="password" autoComplete="off" required value={form.setupKey} disabled={submitting} onChange={(value) => update("setupKey", value)} />
          <Field label="Administrator name" autoComplete="name" required value={form.fullName} disabled={submitting} onChange={(value) => update("fullName", value)} />
          <Field label="Administrator email" type="email" autoComplete="email" required value={form.email} error={emailError || undefined} disabled={submitting} onChange={(value) => update("email", value)} />
          <PasswordField label="Password" required value={form.password} disabled={submitting} error={form.password ? passwordPolicyError(form.password) : undefined} onChange={(value) => update("password", value)} />
          <PasswordField label="Confirm password" confirm required value={form.confirmPassword} disabled={submitting} error={form.confirmPassword && form.password !== form.confirmPassword ? "Passwords do not match." : undefined} onChange={(value) => update("confirmPassword", value)} />
          {error && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{error}</p>}
          {message && <p role="status" className="rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176B66]">{message}</p>}
          <button type="submit" disabled={submitting} className={`${AUTH_PRIMARY} min-h-[46px] w-full`}>{submitting ? "Creating administrator..." : "Create Administrator"}</button>
          <button type="button" disabled={submitting} onClick={onBack} className="w-full text-sm font-semibold text-[#176B66] underline">Back to Login</button>
        </form>}
      </div>
    </AuthLayout>
  );
}

export default function App() {
  useModalFocusManager();
  const [page, setPage] = useState<string>("in");
  const [authMode, setAuthMode] = useState<AuthMode>(() => appPathname() === "/signup" ? "signup" : "signin");
  const [authTransitioning, setAuthTransitioning] = useState(false);
  const authTransitionTimerRef = useRef<number | null>(null);
  const [authUser, setAuthUser] = useState<SafeUser | null>(null);
  const authUserRef = useRef<SafeUser | null>(null);
  useEffect(() => { authUserRef.current = authUser; }, [authUser]);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");
  const [firstAdminSetupAvailable, setFirstAdminSetupAvailable] = useState(false);
  const [step, setStep] = useState(1);
  const [notice, setNotice] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [login, setLogin] = useState({ email: "", password: "", confirm: "" });
  const [members, setMembers] = useState<Member[]>([]);
  const [signIn, setSignIn] = useState({ email: "", password: "" });
  const [recoveryView, setRecoveryView] = useState<"forgot" | "reset">(
    () => appPathname() === "/reset-password" ? "reset" : "forgot",
  );
  useEffect(() => {
    const titles: Record<string, string> = {
      welcome: "FYPHub | Welcome",
      in: "FYPHub | Sign In",
      up: "FYPHub | Create Team Account",
      recover: recoveryView === "reset" ? "FYPHub | Reset Password" : "FYPHub | Forgot Password",
      "first-admin": "FYPHub | First Administrator Setup",
      "admin-portal": "FYPHub | Administrator",
      account: authUser?.role === "STUDENT"
        ? "FYPHub | Group"
        : authUser?.role === "SUPERVISOR"
          ? "FYPHub | Supervisor"
          : authUser?.role === "COORDINATOR"
            ? "FYPHub | Coordinator"
            : authUser?.role === "PANEL_MEMBER"
              ? "FYPHub | Evaluator"
              : "FYPHub",
    };
    document.title = titles[page] ?? "FYPHub";
  }, [page, recoveryView, authUser?.role]);
  const [resetToken, setResetToken] = useState(
    () => new URLSearchParams(window.location.search).get("token") ?? "",
  );
  const [recoveryIdentifier, setRecoveryIdentifier] = useState("");
  const [recoverySubmitting, setRecoverySubmitting] = useState(false);
  const [recoveryMessage, setRecoveryMessage] = useState("");
  const [recoveryError, setRecoveryError] = useState("");
  const [resetLink, setResetLink] = useState("");
  const [developmentLinkState, setDevelopmentLinkState] = useState<DevelopmentResetLinkState>("idle");
  const [resetLinkError, setResetLinkError] = useState("");
  const [recoveryStatus, setRecoveryStatus] = useState<PasswordResetDeliveryStatus | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmNewPassword, setConfirmNewPassword] = useState("");
  const [resetSuccess, setResetSuccess] = useState(false);
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [cyclesState, setCyclesState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [cycleId, setCycleId] = useState("");
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [policyState, setPolicyState] = useState<
    "idle" | "loading" | "ready" | "unavailable" | "error"
  >("idle");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState<{
    groupNumber: number | null;
    cycle: string;
  } | null>(null);
  const publicNavigationRef = useRef<(route: PublicRoute, mode?: "push" | "replace" | "pop") => void>(() => undefined);

  useEffect(() => {
    let active = true;
    void fetchFirstAdminSetupAvailable(API)
      .then((isAvailable) => {
        if (active) setFirstAdminSetupAvailable(isAvailable);
      })
      .catch(() => {
        if (active) setFirstAdminSetupAvailable(false);
      });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        let response = await fetch(`${API}/api/v1/academic-cycles`, {
          credentials: "include",
          signal: controller.signal,
        });
        // First hit after a cold API/proxy start can return 503; retry once.
        if (response.status === 503) {
          await new Promise((resolve) => window.setTimeout(resolve, 250));
          response = await fetch(`${API}/api/v1/academic-cycles`, {
            credentials: "include",
            signal: controller.signal,
          });
        }
        if (!response.ok) throw new Error(academicCycleError(response.status));
        const data: Cycle[] = await response.json();
        if (!controller.signal.aborted) {
          const seen = new Set<string>();
          const openCycles = sortCyclesDesc(data).filter((cycle) => {
            if (!cycle.registration_open) return false;
            const key = `${cycle.academic_year ?? ""}|${(cycle.session ?? "").toUpperCase()}|${(cycle.code ?? "").trim().toLowerCase()}|${(cycle.display_name ?? "").trim().toLowerCase()}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          });
          setCycles(openCycles);
          setCyclesState("ready");
        }
      } catch {
        if (!controller.signal.aborted) setCyclesState("error");
      }
    })();
    return () => controller.abort();
  }, []);
  useEffect(() => {
    if (!cycleId) {
      queueMicrotask(() => {
        setPolicy(null);
        setPolicyState("idle");
      });
      return;
    }
    const controller = new AbortController();
    queueMicrotask(() => {
      setPolicy(null);
      setPolicyState("loading");
    });
    void (async () => {
      try {
        const response = await fetch(
          `${API}/api/v1/academic-cycles/${cycleId}/group-policy`,
          { credentials: "include", signal: controller.signal },
        );
        if (response.status === 404) {
          if (!controller.signal.aborted) setPolicyState("unavailable");
          return;
        }
        if (!response.ok) throw new Error(academicCycleError(response.status));
        const data: Policy = await response.json();
        if (!controller.signal.aborted) {
          setPolicy(data);
          setPolicyState("ready");
        }
      } catch {
        if (!controller.signal.aborted) setPolicyState("error");
      }
    })();
    return () => controller.abort();
  }, [cycleId]);
  useEffect(() => {
    if (!policy) return;
    queueMicrotask(() => {
      setMembers((current) => {
        if (current.length >= policy.min_group_size) return current;
        return [...current, ...Array.from({ length: policy.min_group_size - current.length }, () => newMember())];
      });
    });
  }, [policy]);
  useEffect(() => {
    if (appPathname() === "/reset-password" || appPathname() === FIRST_ADMIN_SETUP_PATH) return;
    void (async () => {
      try {
        const response = await fetch(`${API}/api/v1/auth/me`, {
          credentials: "include",
        });
        if (response.ok) {
          const user = (await response.json()) as SafeUser;
          const destination = dashboardPageForRole(user.role);
          if (!destination || !user.is_active) {
            setAuthUser(null);
            setAuthError("Your account has no valid dashboard role. Please contact an administrator.");
            publicNavigationRef.current(publicRoute("in"), "replace");
            return;
          }
          setAuthUser(user);
          setPage(destination);
          const homePath = appPath(destination === "admin-portal" ? "/admin" : "/");
          if (appPathname() === "/login" || appPathname() === "/signup") {
            window.history.replaceState({ fyphubNavigation: { page: destination } }, "", homePath);
          }
        }
      } catch {
        /* A local API may not be running while the public signup form is used. */
      }
    })();
  }, []);
  useEffect(() => {
    if (page !== "recover" || recoveryView !== "forgot") return;
    let active = true;
    void fetch(`${API}/api/v1/auth/password-reset-status`)
      .then((response) => response.ok ? response.json() as Promise<PasswordResetDeliveryStatus> : null)
      .then((status) => {
        if (active && status) setRecoveryStatus(status);
      })
      .catch(() => {
        if (active) setRecoveryStatus(null);
      });
    return () => { active = false; };
  }, [page, recoveryView]);
  const selectedCycle = cycles.find((cycle) => String(cycle.id) === cycleId);
  const minimum = policy?.min_group_size ?? 1;
  const maximum = policy?.max_group_size;
  const teamSize = members.length;
  const clear = (key: string) => {
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setNotice("");
  };
  const updateLogin = (field: keyof typeof login, value: string) => {
    setLogin((current) => ({ ...current, [field]: value }));
    clear(`login.${field}`);
  };
  const updateMember = (id: string, field: keyof Omit<Member, "id">, value: string) => {
    setMembers((current) =>
      current.map((member) =>
        member.id === id ? { ...member, [field]: sanitizeMemberValue(field, value) } : member,
      ),
    );
    clear(memberKey(id, field));
  };

  function validate(target: number): FieldErrors {
    const next: FieldErrors = {};
    if (target === 1 || target === 0) {
      if (!cycleId) next["account.cycle"] = "Choose an academic cycle.";
      else if (!selectedCycle?.registration_open)
        next["account.cycle"] = "Registration is closed for this cycle.";
      else if (policyState === "loading")
        next["account.cycle"] = "Group policy is still loading.";
      else if (policyState === "unavailable")
        next["account.cycle"] = "This cycle has no group policy yet.";
      else if (policyState === "error")
        next["account.cycle"] = "Group policy could not be loaded.";
    }
    if (target === 2 || target === 0) {
      const registrations = new Map<string, string>();
      const emails = new Map<string, string>();
      members.forEach((member) => {
        const prefix = `member.${member.id}`;
        const name = member.full_name.trim();
        if (!name) next[`${prefix}.full_name`] = "Enter the member's full name.";
        else if (name.length < 2 || name.length > 100 || /[0-9]/.test(name)) next[`${prefix}.full_name`] = "Name must be 2–100 letters; numbers are not allowed.";
        if (name && !/^\p{L}+(?: +\p{L}+)*$/u.test(name)) next[`${prefix}.full_name`] = "Name must be 2–100 letters and spaces only.";
        const reg = registration(member.registration);
        const emailError = szabistEmailValidationMessage(member.email);
        if (emailError) next[`${prefix}.email`] = emailError;
        if (!reg)
          next[`${prefix}.registration`] = "Enter a registration number.";
        else if (!/^\d+$/.test(reg)) next[`${prefix}.registration`] = "Registration number must contain digits only.";
        const normalizedEmail = normalizeEmail(member.email);
        if (normalizedEmail && emails.has(normalizedEmail)) {
          next[`${prefix}.email`] = "Member emails must be unique in this group.";
          next[emails.get(normalizedEmail)!] = "Member emails must be unique in this group.";
        }
        if (normalizedEmail) emails.set(normalizedEmail, `${prefix}.email`);
        if (reg && registrations.has(reg)) {
          next[`${prefix}.registration`] =
            "Registration number is already used in this team.";
          next[registrations.get(reg)!] =
            "Registration number is already used in this team.";
        }
        if (reg) registrations.set(reg, `${prefix}.registration`);
      });
      if (!maximum)
        next["members.configuration"] =
          "Choose a cycle with an available group policy.";
      if (minimum && teamSize < minimum)
        next["members.configuration"] =
          `This group has ${teamSize} members; the selected cycle requires at least ${minimum}. Add members before submitting.`;
      if (maximum && teamSize > maximum)
        next["members.configuration"] =
          `This team has ${teamSize} members; the selected cycle allows ${maximum}. Remove members before submitting.`;
    }
    if (target === 3 || target === 0) {
      const sharedEmailError = szabistEmailValidationMessage(login.email);
      if (sharedEmailError) next["login.email"] = sharedEmailError;
      const groupPasswordError = passwordPolicyError(login.password);
      if (groupPasswordError) next["login.password"] = groupPasswordError;
      if (login.password !== login.confirm) next["login.confirm"] = "Passwords do not match.";
    }
    return next;
  }
  const stepFor = (key?: string) =>
    !key || key.startsWith("account")
      ? 1
      : key.startsWith("member") || key.startsWith("members")
        ? 2
        : key.startsWith("login")
          ? 3
          : 1;
  function navigatePublic(route: PublicRoute, mode: "push" | "replace" | "pop" = "push") {
    let next = publicRoute(route.page, route.signupRole, route.step, route.studentMode);
    let nextErrors: FieldErrors = {};
    if (next.page === "up" && next.signupRole === "STUDENT" && next.studentMode === "group" && next.step > 1) {
      nextErrors = validate(1);
      if (!Object.keys(nextErrors).length && next.step > 2) nextErrors = validate(2);
      if (Object.keys(nextErrors).length) {
        next = publicRoute("up", "STUDENT", Math.min(...Object.keys(nextErrors).map(stepFor)) as 1 | 2 | 3, "group");
      }
    }
    setPage(next.page);
    if (next.page === "in" || next.page === "up") {
      setAuthMode(next.page === "up" ? "signup" : "signin");
    }
    setStep(next.step);
    setErrors(nextErrors);
    setNotice(Object.keys(nextErrors).length ? validationNotice(nextErrors, members) : "");
    const current = readPublicRoute(window.history.state);
    const changed = !current || current.page !== next.page || current.signupRole !== next.signupRole || current.step !== next.step || current.studentMode !== next.studentMode;
    const publicPath = appPath(
      next.page === "welcome"
        ? welcomePublicPath()
        : next.page === "up"
          ? "/signup"
          : next.page === "recover"
            ? "/recover"
            : "/login",
    );
    if (mode === "push" && changed) window.history.pushState({ fyphubNavigation: next }, "", publicPath);
    if ((mode === "replace" || (mode === "pop" && changed)) && changed) window.history.replaceState({ fyphubNavigation: next }, "", publicPath);
  }
  useEffect(() => {
    publicNavigationRef.current = navigatePublic;
  });
  useEffect(() => {
    if (page !== "up") return;
    const frame = window.requestAnimationFrame(() => {
      // Signup steps can change height substantially (especially when member
      // cards are added). Reset both possible scroll owners so the stepper and
      // cycle/structure heading never remain above the viewport after a step
      // transition or browser scroll anchoring adjustment.
      window.scrollTo({ top: 0, left: 0, behavior: "auto" });
      document.querySelector<HTMLElement>(".auth-form-panel")?.scrollTo({
        top: 0,
        left: 0,
        behavior: "auto",
      });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [page, step]);
  useEffect(() => {
    const pathname = appPathname();
  const stored = readPublicRoute(window.history.state);
    let initial = stored ?? (isLandingPath(pathname) ? publicRoute("welcome") : publicRoute("in"));
    if (isLandingPath(pathname) && stored?.page === "in") {
      initial = publicRoute("welcome");
    }
    if (pathname === "/recover") {
      initial = publicRoute("recover");
    }
    if (pathname === "/signup") {
      initial = publicRoute("up");
    }
    if (appPathname() === FIRST_ADMIN_SETUP_PATH) {
      queueMicrotask(() => setPage("first-admin"));
      window.history.replaceState({ fyphubSetup: true }, "", appPath(FIRST_ADMIN_SETUP_PATH));
    } else if (appPathname() === "/reset-password") {
      queueMicrotask(() => {
        setRecoveryView("reset");
        setResetToken(new URLSearchParams(window.location.search).get("token") ?? "");
        setPage("recover");
      });
      window.history.replaceState({ fyphubNavigation: publicRoute("recover") }, "", window.location.href);
    } else if (pathname === "/recover") {
      queueMicrotask(() => {
        setRecoveryView("forgot");
        setPage("recover");
      });
      window.history.replaceState({ fyphubNavigation: publicRoute("recover") }, "", appPath("/recover"));
    } else if (pathname === "/signup") {
      queueMicrotask(() => {
        setPage("up");
        setStep(1);
      });
      window.history.replaceState({ fyphubNavigation: publicRoute("up") }, "", appPath("/signup"));
    } else {
      if (!readPublicRoute(window.history.state)) window.history.replaceState({ fyphubNavigation: initial }, "", window.location.href);
      publicNavigationRef.current(initial, "pop");
    }
    const onPopState = (event: PopStateEvent) => {
      const destination = (event.state as { fyphubNavigation?: { page?: string } } | null)?.fyphubNavigation?.page;
      if (isDashboardPage(destination)) {
        const user = authUserRef.current;
        const permitted = user ? dashboardPageForRole(user.role) : null;
        if (!permitted) {
          setAuthUser(null);
          publicNavigationRef.current(publicRoute("in"), "replace");
          return;
        }
        if (destination !== permitted) {
          window.history.replaceState({ fyphubNavigation: { page: permitted } }, "", window.location.href);
        }
        setPage(permitted);
        return;
      }
      publicNavigationRef.current(
        readPublicRoute(event.state) ?? (isLandingPath(appPathname()) ? publicRoute("welcome") : publicRoute("in")),
        "pop",
      );
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  function nextStep() {
    const next = validate(step);
    setErrors(next);
    if (Object.keys(next).length) {
      setNotice(validationNotice(next, members));
      return;
    }
    navigatePublic(publicRoute("up", "STUDENT", Math.min(3, step + 1) as 1 | 2 | 3, "group"));
  }
  function mapPath(path?: string) {
    if (!path) return undefined;
    const basic: Record<string, string> = {
      shared_login_email: "login.email",
      group_email: "login.email",
      password: "login.password",
      academic_cycle_id: "account.cycle",
      members: "members.configuration",
    };
    if (basic[path]) return basic[path];
    const match = path.match(
      /^members\.(\d+)\.(full_name|email|registration_number)$/,
    );
    if (!match || !members[Number(match[1])]) return undefined;
    const field = {
      full_name: "full_name",
      email: "email",
      registration_number: "registration",
    }[match[2]] as keyof Omit<Member, "id">;
    return memberKey(members[Number(match[1])].id, field);
  }
  function applyError(detail: ApiDetail) {
    const fields: Array<{ key: string; code?: string }> = [
      ...(detail.field ? [{ path: detail.field }] : []),
      ...(detail.fields ?? []),
    ]
      .flatMap((item) => {
        const key = mapPath(item.path);
        return key ? [{ key, code: item.code }] : [];
      });
    if (fields.length) {
      const nextErrors = Object.fromEntries(
        fields.map(({ key, code }) => [key, apiFieldErrorMessage(key, detail.message, code)]),
      );
      setErrors(nextErrors);
      setStep(Math.min(...fields.map(({ key }) => stepFor(key))));
      setNotice(validationNotice(nextErrors, members));
      return;
    }
    setNotice(detail.message ?? "Student group account could not be created.");
  }
  const canSubmit = Boolean(
    selectedCycle?.registration_open &&
      policyState === "ready" &&
      maximum &&
      teamSize <= maximum &&
      Object.keys(validate(0)).length === 0,
  );
  async function submit() {
    const next = validate(0);
    if (Object.keys(next).length) {
      setErrors(next);
      setStep(stepFor(Object.keys(next)[0]));
      setNotice(validationNotice(next, members));
      return;
    }
    if (submitting || !cycleId) return;
    setSubmitting(true);
    setNotice("");
    setErrors({});
    const payload = {
      academic_cycle_id: Number(cycleId),
      group_email: normalizeEmail(login.email),
      password: login.password,
      confirm_password: login.confirm,
      members: members.map((member) => ({
        full_name: member.full_name.trim(),
        email: normalizeEmail(member.email),
        registration_number: registration(member.registration),
      })),
    };
    try {
      const response = await fetch(`${API}/api/v1/auth/group-signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        applyError((data.detail ?? {}) as ApiDetail);
        return;
      }
      setSuccess({
        groupNumber: (data.team.group_number as number | null | undefined) ?? null,
        cycle: data.cycle.display_name as string,
      });
      setLogin((current) => ({ ...current, password: "", confirm: "" }));
    } catch {
      setNotice(
        "The registration service is unavailable. Your entered details were kept.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function performLogin() {
    if (authSubmitting) return;
    const identifier = signIn.email.trim();
    if (!identifier || !signIn.password) {
      setAuthError(
        "Enter the group email and password.",
      );
      return;
    }
    const identifierError = emailValidationMessage(identifier);
    if (identifierError) {
      setAuthError(identifierError);
      return;
    }
    setAuthSubmitting(true);
    setAuthError("");
    const payload = { email: normalizeEmail(identifier), password: signIn.password };
    try {
      const response = await fetch(`${API}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        setAuthError(
          response.status === 401
            ? "The email or password is incorrect, or the account is inactive."
            : "Sign in could not be completed. Please check your details.",
        );
        return;
      }
      const loginUser = (await response.json()) as SafeUser;
      const loginDestination = dashboardPageForRole(loginUser.role);
      if (!loginDestination || !loginUser.is_active) {
        setAuthUser(null);
        setAuthError("Your account has no valid dashboard role. Please contact an administrator.");
        return;
      }
      const sessionResponse = await fetch(`${API}/api/v1/auth/me`, {
        credentials: "include",
      });
      if (!sessionResponse.ok) {
        setAuthUser(null);
        setAuthError(
          sessionResponse.status === 401
            ? "Sign-in succeeded, but the browser session could not be confirmed. Please try again."
            : "The authenticated session could not be confirmed.",
        );
        return;
      }
      const confirmedUser = (await sessionResponse.json()) as SafeUser;
      const destination = dashboardPageForRole(confirmedUser.role);
      if (!destination || !confirmedUser.is_active) {
        setAuthUser(null);
        setAuthError("Your account has no valid dashboard role. Please contact an administrator.");
        return;
      }
      setAuthUser(confirmedUser);
      setSignIn({ email: "", password: "" });
      const homePath = appPath(destination === "admin-portal" ? "/admin" : "/");
      window.history.pushState({ fyphubNavigation: { page: destination } }, "", homePath);
      setPage(destination);
    } catch {
      setAuthError(
        "The sign-in service is unavailable. Please try again shortly.",
      );
    } finally {
      setAuthSubmitting(false);
    }
  }
  function recoveryIdentifierError(value: string): string {
    const identifier = value.trim();
    if (!identifier) return "Enter your email or registration ID.";
    return identifier.includes("@")
      ? emailValidationMessage(identifier) ?? ""
      : "";
  }
  async function requestPasswordReset() {
    if (recoverySubmitting) return;
    const identifierError = recoveryIdentifierError(recoveryIdentifier);
    if (identifierError) {
      setRecoveryError(identifierError);
      setRecoveryMessage("");
      return;
    }
    const normalizedIdentifier = recoveryIdentifier.trim().toLowerCase();
    setRecoverySubmitting(true);
    setRecoveryError("");
    setRecoveryMessage("");
    setResetLink("");
    setDevelopmentLinkState("idle");
    setResetLinkError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier: normalizedIdentifier }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setRecoveryError(PASSWORD_RESET_GENERIC_MESSAGE);
        return;
      }
      setRecoveryMessage(body.message ?? "If an account exists, a password reset link will be sent.");
      const isLocalUi = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1" || window.location.hostname === "::1";
      let status = recoveryStatus;
      if (!status) {
        try {
          const statusResponse = await fetch(`${API}/api/v1/auth/password-reset-status`);
          if (statusResponse.ok) {
            const statusBody = await statusResponse.json() as Partial<PasswordResetDeliveryStatus>;
            if (typeof statusBody.development_mode === "boolean" && typeof statusBody.smtp_configured === "boolean") {
              status = statusBody as PasswordResetDeliveryStatus;
              setRecoveryStatus(status);
            }
          }
        } catch {
          status = null;
        }
      }
      if (!isLocalUi) return;
      if (!status) {
        setDevelopmentLinkState("error");
        setResetLinkError("Reset link is not available right now. Please request again.");
        return;
      }
      if (!status.development_mode || status.smtp_configured) return;
      setDevelopmentLinkState("loading");
      try {
        const developmentResponse = await fetch(`${API}/api/v1/auth/dev/password-reset-link?identifier=${encodeURIComponent(normalizedIdentifier)}`);
        const developmentBody = await developmentResponse.json().catch(() => ({}));
        if (developmentResponse.ok && typeof developmentBody.reset_link === "string" && developmentBody.reset_link.trim()) {
          setResetLink(developmentBody.reset_link);
          setDevelopmentLinkState("ready");
        } else if (developmentResponse.status === 404) {
          setDevelopmentLinkState("missing");
          setResetLinkError("Reset link is not available right now. Please request again.");
        } else {
          setDevelopmentLinkState("error");
          setResetLinkError("Reset link is not available right now. Please request again.");
        }
      } catch {
        setDevelopmentLinkState("error");
        setResetLinkError("Reset link is not available right now. Please request again.");
      }
    } catch {
      setRecoveryError("The password reset service is unavailable. Please try again shortly.");
    } finally {
      setRecoverySubmitting(false);
    }
  }
  async function submitPasswordReset() {
    if (recoverySubmitting) return;
    if (!resetToken) {
      setRecoveryError("This password reset link is missing its token.");
      return;
    }
    const passwordError = passwordPolicyError(newPassword);
    if (passwordError) {
      setRecoveryError(passwordError);
      return;
    }
    if (newPassword !== confirmNewPassword) {
      setRecoveryError("Passwords do not match.");
      return;
    }
    setRecoverySubmitting(true);
    setRecoveryError("");
    try {
      const response = await fetch(`${API}/api/v1/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: resetToken, password: newPassword }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setRecoveryError(typeof body.detail?.message === "string" ? body.detail.message : "This password reset link is invalid or has expired.");
        return;
      }
      setResetSuccess(true);
      setRecoveryMessage(body.message ?? "Password reset successful. Please log in again.");
      setNewPassword("");
      setConfirmNewPassword("");
    } catch {
      setRecoveryError("The password reset service is unavailable. Please try again shortly.");
    } finally {
      setRecoverySubmitting(false);
    }
  }
  async function signOut() {
    try {
      await fetch(`${API}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      setAuthUser(null);
      setSignIn({ email: "", password: "" });
      setAuthError("");
      window.history.replaceState({ fyphubNavigation: publicRoute("in") }, "", appPath("/login"));
      navigatePublic(publicRoute("in"), "replace");
    }
  }

  const switchAuthMode = (nextMode: AuthMode) => {
    if (authTransitioning || authMode === nextMode) return;
    if (authTransitionTimerRef.current !== null) {
      window.clearTimeout(authTransitionTimerRef.current);
    }
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setAuthMode(nextMode);
    setAuthTransitioning(!reducedMotion);
    authTransitionTimerRef.current = window.setTimeout(() => {
      authTransitionTimerRef.current = null;
      setAuthTransitioning(false);
      navigatePublic(publicRoute(nextMode === "signup" ? "up" : "in"));
    }, reducedMotion ? 0 : AUTH_SWITCH_DURATION);
  };
  useEffect(() => () => {
    if (authTransitionTimerRef.current !== null) window.clearTimeout(authTransitionTimerRef.current);
  }, []);
  if (page === "welcome" && !authUser) {
    return (
      <WelcomeLanding
        onLogin={() => navigatePublic(publicRoute("in"))}
        onSignup={() => navigatePublic(publicRoute("up"))}
      />
    );
  }
  if (page === "account" && authUser?.role === "STUDENT")
    return (
      <StudentPortal api={API} user={authUser} onLogout={() => void signOut()} />
    );
  if (page === "account" && authUser?.role === "SUPERVISOR")
    return (
      <SupervisorPortal api={API} user={authUser} onLogout={() => void signOut()} />
    );
  if (page === "account" && authUser?.role === "COORDINATOR")
    return (
      <CoordinatorPortal api={API} user={authUser} onLogout={() => void signOut()} />
    );
  if (page === "account" && authUser?.role === "PANEL_MEMBER")
    return <EvaluatorPortal api={API} user={authUser} onLogout={() => void signOut()} />;
  if ((page === "account" || page === "admin-portal") && authUser && !dashboardPageForRole(authUser.role)) {
    return (
      <AuthLayout compact>
        <div className="space-y-4">
          <h1 className="text-2xl font-bold">Dashboard unavailable</h1>
          <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">Your account has no recognized dashboard role. Please contact an administrator.</p>
          <button type="button" onClick={() => void signOut()} className={`${AUTH_PRIMARY} w-full`}>Log out</button>
        </div>
      </AuthLayout>
    );
  }
  if (page === "account" && authUser && dashboardPageForRole(authUser.role) === "account")
    return (
      <main className="min-h-screen bg-[#F7F5EF] px-4 py-8 text-[#243746]">
        <div className="mx-auto max-w-md">
          <header className="mb-7">
            <Logo />
          </header>
          <section className="rounded-2xl border border-[#dce4de] bg-white p-6 shadow-[0_8px_30px_rgba(36,55,70,0.04)]">
            <p className="text-sm font-semibold text-[#3984E8]">
              Authenticated account
            </p>
            <h1 className="mt-1 text-2xl font-bold">
              Welcome, {authUser.full_name}
            </h1>
            <p className="mt-3 text-sm text-[#4f6470]">{authUser.email}</p>
            <dl className="mt-5 grid gap-3 rounded-xl bg-[#f4f8f5] p-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt>Role</dt>
                <dd className="font-semibold">{authUser.role}</dd>
              </div>
              {authUser.registration_number && (
                <div className="flex justify-between gap-4">
                  <dt>Registration ID</dt>
                  <dd className="font-semibold">
                    {authUser.registration_number}
                  </dd>
                </div>
              )}
            </dl>
            <p className="mt-5 text-sm text-[#4f6470]">
              Your role dashboard is not available in this project yet.
            </p>
            <button
              type="button"
              onClick={() => void signOut()}
              className={`${PRIMARY} mt-6 w-full`}
            >
              Log out
            </button>
          </section>
        </div>
      </main>
    );
  if (page === "admin" && authUser)
    return (
      <main className="min-h-screen bg-[#F7F5EF] text-[#243746]">
        <header className="flex items-center justify-between border-b border-[#dce4de] bg-white px-4 py-3 sm:px-6">
          <Logo compact />
          <div className="flex items-center gap-3">
            <span className="hidden text-sm text-[#4f6470] sm:inline">
              {authUser.full_name}
            </span>
            <button
              type="button"
              onClick={() => void signOut()}
              className="text-sm font-semibold text-[#176B66] underline"
            >
              Log out
            </button>
          </div>
        </header>
        <div className="mx-auto flex max-w-6xl flex-col md:flex-row">
          <aside className="border-b border-[#dce4de] bg-white p-4 md:min-h-[calc(100vh-65px)] md:w-60 md:border-b-0 md:border-r">
            <nav aria-label="Admin navigation" className="grid gap-1">
              {[
                "Overview",
                "Users & Roles",
                "Academic Cycles",
                "Supervisor Capacity",
                "Deadlines",
                "Reminders & Escalations",
              ].map((item, index) => (
                <span
                  key={item}
                  className={`rounded-lg px-3 py-2 text-sm ${index === 0 ? "bg-[#eaf2ff] font-semibold text-[#176B66]" : "text-[#4f6470]"}`}
                >
                  {item}
                </span>
              ))}
            </nav>
          </aside>
          <section className="flex-1 p-5 sm:p-8">
            <h1 className="mt-1 text-2xl font-bold">Overview</h1>
            <p className="mt-3 max-w-xl text-sm text-[#4f6470]">
              Your session is verified. Management data and
              controls will be added checkpoint by checkpoint; no statistics or
              management actions are shown until backed by real APIs.
            </p>
            <dl className="mt-6 max-w-md rounded-xl border border-[#dce4de] bg-white p-4 text-sm">
              <div className="flex justify-between gap-4">
                <dt>Account</dt>
                <dd className="font-semibold">{authUser.email}</dd>
              </div>
              <div className="mt-3 flex justify-between gap-4">
                <dt>Role</dt>
                <dd className="font-semibold">{authUser.role}</dd>
              </div>
            </dl>
          </section>
        </div>
      </main>
    );
  if (page === "admin-portal" && authUser && dashboardPageForRole(authUser.role) === "admin-portal")
    return (
      <AdminPortal api={API} user={authUser} onLogout={() => void signOut()} />
    );
  if (page === "first-admin")
    return (
      <FirstAdminSetup
        api={API}
        onComplete={(email) => {
          setSignIn({ email, password: "" });
          setAuthError("");
          setPage("in");
          setAuthMode("signin");
          window.history.replaceState({ fyphubNavigation: publicRoute("in") }, "", appPath("/login"));
        }}
        onBack={() => {
          setPage("in");
          setAuthMode("signin");
          window.history.replaceState({ fyphubNavigation: publicRoute("in") }, "", appPath("/login"));
        }}
      />
    );
  if (page === "recover")
    return (
      <AuthLayout compact>
        {recoveryView === "forgot" ? (
          <form onSubmit={(event) => { event.preventDefault(); void requestPasswordReset(); }} className="space-y-4">
            <h1 className="text-[26px] font-bold sm:text-[28px]">Forgot Password?</h1>
            <p className="text-sm text-[#4f6470]">Enter your email or registration ID and, if an account exists, we will send a reset link.</p>
            {recoveryStatus?.development_mode && !recoveryStatus.smtp_configured && <p role="status" className="rounded-lg bg-[#eaf2ff] px-3 py-2 text-sm text-[#243746]">Development mode is active. After requesting a reset, you can open the local reset link here.</p>}
            {recoveryStatus && !recoveryStatus.development_mode && !recoveryStatus.smtp_configured && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">Password recovery email delivery is not configured for this project.</p>}
            <Field
              label="Email or Registration ID"
              type={recoveryIdentifier.includes("@") ? "email" : "text"}
              autoComplete="username"
              value={recoveryIdentifier}
              disabled={recoverySubmitting}
              error={recoveryIdentifier ? recoveryIdentifierError(recoveryIdentifier) : undefined}
              onChange={(value) => {
                setRecoveryIdentifier(value);
                setRecoveryError("");
                setRecoveryMessage("");
                setResetLink("");
                setDevelopmentLinkState("idle");
                setResetLinkError("");
              }}
            />
            {recoveryError && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{recoveryError}</p>}
            {recoveryMessage && <p role="status" className="rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176B66]">{recoveryMessage}</p>}
            {developmentLinkState === "loading" && <p role="status" className="rounded-lg bg-[#eaf2ff] px-3 py-2 text-sm text-[#243746]">Loading local development reset link...</p>}
            {resetLinkError && developmentLinkState !== "ready" && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{resetLinkError}</p>}
            {developmentLinkState === "ready" && resetLink && <div className="space-y-2 rounded-lg border border-[#b9ddcf] bg-[#f4fbf7] p-3" role="status"><p className="break-all text-sm text-[#243746]">Development reset link: {resetLink}</p><button type="button" onClick={() => window.location.assign(resetLink)} className={`${AUTH_PRIMARY} w-full`}>Open reset link</button></div>}
            <button type="submit" disabled={recoverySubmitting || Boolean(recoveryIdentifierError(recoveryIdentifier))} className={`${AUTH_PRIMARY} min-h-[46px] w-full`}>{recoverySubmitting ? "Requesting..." : "Request reset link"}</button>
            <button type="button" disabled={recoverySubmitting} onClick={() => { setRecoveryIdentifier(""); navigatePublic(publicRoute("in")); }} className="w-full text-sm font-semibold text-[#176B66] underline">Back to Login</button>
          </form>
        ) : (
          <form onSubmit={(event) => { event.preventDefault(); void submitPasswordReset(); }} className="space-y-4">
            <h1 className="text-[26px] font-bold sm:text-[28px]">Reset Password</h1>
            {!resetToken && !resetSuccess && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">This password reset link is missing its token.</p>}
            {!resetSuccess && resetToken && <>
              <PasswordField label="New password" value={newPassword} guidance disabled={recoverySubmitting} error={recoveryError && !newPassword ? recoveryError : undefined} onChange={(value) => { setNewPassword(value); setRecoveryError(""); }} />
              <PasswordField label="Confirm new password" value={confirmNewPassword} confirm disabled={recoverySubmitting} error={newPassword !== confirmNewPassword && confirmNewPassword ? "Passwords do not match." : undefined} onChange={(value) => { setConfirmNewPassword(value); setRecoveryError(""); }} />
              {recoveryError && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{recoveryError}</p>}
              <button type="submit" disabled={recoverySubmitting || Boolean(passwordPolicyError(newPassword)) || newPassword !== confirmNewPassword} className={`${AUTH_PRIMARY} min-h-[46px] w-full`}>{recoverySubmitting ? "Resetting..." : "Reset Password"}</button>
            </>}
            {resetSuccess && recoveryMessage && <p role="status" className="rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176B66]">{recoveryMessage}</p>}
            <button type="button" disabled={recoverySubmitting} onClick={() => { setRecoveryIdentifier(""); navigatePublic(publicRoute("in")); }} className="w-full text-sm font-semibold text-[#176B66] underline">Back to Login</button>
          </form>
        )}
      </AuthLayout>
    );
  if (page === "up" && success)
    return (
      <AuthLayout>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-[#176B66]">
              Student group account created successfully.
            </h1>
            <p className="mt-3 text-sm text-[#4f6470]">
              {success.groupNumber ? `Group ${success.groupNumber}. ` : "Your group has been assigned. "}
              Academic cycle: {success.cycle}. Your group login is ready.
            </p>
            <button
              type="button"
              onClick={() => navigatePublic(publicRoute("in"))}
              className={`${AUTH_PRIMARY} mt-6 w-full`}
            >
              Go to Login
            </button>
          </div>
      </AuthLayout>
    );
  if (page === "in" || page === "up")
    return (
      <AuthLayout authMode={authMode} transitioning={authTransitioning}>
          <div className="auth-form-views auth-form-layer">
          <div
            className={`auth-form-view signin-form auth-form-view--signin ${authMode === "signin" ? "is-active" : ""}`}
            aria-hidden={authMode !== "signin"}
            inert={authMode !== "signin" ? true : undefined}
          >
          <div>
            <h1 className="auth-card__title">Welcome back</h1>
            <p className="auth-card__hint mt-1.5 mb-4 text-sm">
              Sign in gently — your team workspace is waiting.
            </p>
            <form
              className="mt-5 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void performLogin();
              }}
            >
              <Field
                label="Email"
                type="email"
                autoComplete="username"
                required
                value={signIn.email}
                error={signIn.email.includes("@") ? emailValidationMessage(signIn.email) : undefined}
                disabled={authSubmitting}
                onChange={(value) => {
                  setSignIn((current) => ({ ...current, email: value }));
                  setAuthError("");
                }}
              />
              <PasswordField
                label="Password"
                autoComplete="current-password"
                required
                value={signIn.password}
                disabled={authSubmitting}
                onChange={(value) => {
                  setSignIn((current) => ({ ...current, password: value }));
                  setAuthError("");
                }}
              />
              <div className="flex justify-end text-sm">
                <button
                  type="button"
                  onClick={() => { setRecoveryView("forgot"); setResetToken(""); setResetSuccess(false); setRecoveryIdentifier(""); setRecoveryMessage(""); setRecoveryError(""); setResetLink(""); setDevelopmentLinkState("idle"); setResetLinkError(""); navigatePublic(publicRoute("recover")); }}
                  className="auth-card__link font-semibold underline"
                >
                  Forgot Password?
                </button>
              </div>
              {authError && (
                <p
                  role="alert"
                  className="rounded-lg px-3 py-2 text-sm"
                >
                  {authError}
                </p>
              )}
              <button
                type="submit"
                disabled={
                  authSubmitting ||
                  Boolean(
                    signIn.email.includes("@") &&
                      emailValidationMessage(signIn.email),
                  )
                }
                className={`${AUTH_PRIMARY} min-h-[46px] w-full`}
              >
                {authSubmitting ? "Signing in..." : "Login"}
              </button>
              <p className="auth-card__hint text-center text-sm">
                Don&apos;t have an account?{" "}
                <button
                  type="button"
                  onClick={(event) => { event.preventDefault(); switchAuthMode("signup"); }}
                  className="auth-card__link font-semibold underline"
                >
                  Create an account
                </button>
              </p>
              {firstAdminSetupAvailable && (
                <p className="auth-card__hint text-center text-sm">
                  First-time administrator?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      window.history.pushState({ fyphubSetup: true }, "", appPath(FIRST_ADMIN_SETUP_PATH));
                      setPage("first-admin");
                    }}
                    className="auth-card__link font-semibold underline"
                  >
                    Set up administrator
                  </button>
                </p>
              )}
            </form>
          </div>
          </div>
          <div
            className={`auth-form-view signup-form auth-form-view--signup ${authMode === "signup" ? "is-active" : ""}`}
            aria-hidden={authMode !== "signup"}
            inert={authMode !== "signup" ? true : undefined}
          >
            <div className="auth-signup-head">
              <h1 className="text-center text-lg font-bold">
              Create Student Group Account
              </h1>
              <p className="mt-2 mb-6 text-center text-sm text-[#4f6470]">
                Your team will use one verified <span className="font-semibold">@szabist-isb.pk</span> email and password.
              </p>
              <Stepper
                className="auth-signup-stepper"
                steps={STEPS.map((label, index) => ({ id: SIGNUP_STEP_IDS[index], label }))}
                currentStepId={SIGNUP_STEP_IDS[step - 1]}
                completedStepIds={SIGNUP_STEP_IDS.filter((_, index) => index < step - 1)}
              />
              <div className="auth-signup-section-heading">
                <div>
                  <p className="auth-signup-section-kicker">Step {step} of {STEPS.length}</p>
                  <h2 className="auth-signup-section-title">{STEPS[step - 1]}</h2>
                </div>
                <p className="auth-signup-required-note"><span aria-hidden="true">*</span> Required fields</p>
              </div>
            </div>
              {step === 1 && (
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="sm:col-span-2 grid gap-2">
                    <label
                      htmlFor="academic-cycle"
                      className="text-sm font-semibold"
                    >
                      Academic cycle <span className="auth-field__required" aria-hidden="true">*</span>
                    </label>
                    <select
                      id="academic-cycle"
                      value={cycleId}
                      disabled={submitting || cyclesState === "loading"}
                      aria-invalid={Boolean(errors["account.cycle"])}
                      aria-required="true"
                      required
                      className={`${INPUT} ${errors["account.cycle"] ? "border-[#a43a33]" : ""}`}
                      onChange={(event) => {
                        setCycleId(event.target.value);
                        clear("account.cycle");
                      }}
                    >
                      <option value="">
                        {cyclesState === "loading"
                          ? "Loading cycles..."
                          : "Select a cycle"}
                      </option>
                      {cycles.map((cycle) => (
                        <option key={cycle.id} value={cycle.id}>
                          {formatCycleLabel(cycle)}
                        </option>
                      ))}
                    </select>
                    {cyclesState === "error" && (
                      <p className="text-sm text-[#a43a33]">
                        Academic cycles could not be loaded.
                      </p>
                    )}
                    {cyclesState === "ready" && cycles.length === 0 && (
                      <p className="text-sm text-[#a43a33]">
                        No academic cycles are available.
                      </p>
                    )}
                    {errors["account.cycle"] && (
                      <p className="text-sm text-[#a43a33]">
                        {errors["account.cycle"]}
                      </p>
                    )}
                    {selectedCycle && policyState === "ready" && maximum && (
                      <p className="text-sm text-[#4f6470]">
                        This cycle allows {minimum}–{maximum} group members.
                      </p>
                    )}
                  </div>
                </div>
              )}
              {step === 2 && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3"><p className="min-w-0 flex-1 overflow-visible py-0.5 text-sm leading-5 text-[#4f6470]">{teamSize} of {maximum ?? "—"} members added</p><button type="button" disabled={submitting || !maximum || teamSize >= maximum} onClick={() => setMembers((current) => [...current, newMember()])} className="shrink-0 rounded-lg border border-[#176B66] px-3 py-2 text-sm font-semibold text-[#176B66] disabled:cursor-not-allowed disabled:border-[#cbd6d0] disabled:text-[#4f6470]">+ Add member</button></div>
                  {maximum && teamSize >= maximum && <p className="text-sm text-[#4f6470]">Maximum group size reached for this cycle.</p>}
                  {errors["members.configuration"] && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{errors["members.configuration"]}</p>}
                  {members.map((member, index) => (
                    <Card key={member.id} padding="md" className="auth-member-card">
                      <div className="auth-member-card__head">
                        <h3 className="auth-member-card__title">Member {index + 1}</h3>
                        <button
                          type="button"
                          disabled={submitting || members.length <= minimum}
                          aria-label={`Remove Member ${index + 1}`}
                          onClick={() => setMembers((current) => current.filter((item) => item.id !== member.id))}
                          className="auth-member-card__remove"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="auth-member-card__grid">
                         <Field label="Full name" required value={member.full_name} inputMode="text" maxLength={100} disabled={submitting} error={errors[memberKey(member.id, "full_name")]} onChange={(value) => updateMember(member.id, "full_name", value)} />
                         <Field label="Member email" type="email" required value={member.email} disabled={submitting} error={errors[memberKey(member.id, "email")]} onChange={(value) => updateMember(member.id, "email", value)} />
                         <Field label="Registration number" required value={member.registration} inputMode="numeric" pattern="[0-9]*" maxLength={100} disabled={submitting} error={errors[memberKey(member.id, "registration")]} onChange={(value) => updateMember(member.id, "registration", value)} />
                      </div>
                    </Card>
                  ))}
                </div>
              )}
              {step === 3 && (
                <div className="space-y-4">
                   <p className="text-sm text-[#4f6470]">Only exact SZABIST university email addresses ending in <span className="font-semibold">@szabist-isb.pk</span> are accepted.</p>
                   <Field label="Email" type="email" required autoComplete="username" value={login.email} disabled={submitting} error={errors["login.email"]} onChange={(value) => updateLogin("email", value)} />
                   <PasswordField label="Password" required value={login.password} disabled={submitting} error={errors["login.password"]} onChange={(value) => updateLogin("password", value)} />
                   <PasswordField label="Confirm password" required value={login.confirm} disabled={submitting} error={errors["login.confirm"]} onChange={(value) => updateLogin("confirm", value)} />
                </div>
              )}
              {notice && (
                <p
                  role="alert"
                  aria-live="assertive"
                  className="auth-signup-notice mt-5 rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]"
                >
                  {notice}
                </p>
              )}
              <div className="auth-signup-actions">
                {step > 1 && (
                  <Button variant="secondary" disabled={submitting} onClick={() => window.history.back()}>
                    Back
                  </Button>
                )}
                {step < 3 ? (
                  <Button className="auth-signup-actions__primary" disabled={submitting} onClick={nextStep}>
                    Next
                  </Button>
                ) : (
                  <Button className="auth-signup-actions__primary" disabled={submitting || !canSubmit} onClick={() => void submit()}>
                    {submitting ? "Creating..." : "Create Student Group Account"}
                  </Button>
                )}
              </div>
              <p className="auth-switch-link">
                Already have an account?{" "}
                <button type="button" onClick={(event) => { event.preventDefault(); switchAuthMode("signin"); }} className="auth-card__link font-semibold underline">
                  Sign in
                </button>
              </p>
          </div>
        </div>
      </AuthLayout>
    );
  return null;
}
