import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { AdminPortal } from "./AdminPortal";
import { PasswordField } from "./PasswordField";
import { passwordPolicyError } from "./passwordPolicy";
import {
  emailValidationMessage,
  normalizeEmail,
} from "./emailValidation";
import { StudentPortal } from "./portals/student/StudentPortal";
import { SupervisorPortal } from "./portals/supervisor/SupervisorPortal";
import { CoordinatorPortal } from "./portals/coordinator/CoordinatorPortal";
import { StudentEvaluatorPortal as EvaluatorPortal } from "./portals/student/modules/StudentEvaluatorPortal";
import signInStudentsImage from "./assets/sign-in-students.webp";

type Member = { id: string; email: string; registration: string };
type Cycle = {
  id: number;
  code: string;
  display_name: string;
  academic_year?: number | null;
  session?: string | null;
  registration_open: boolean;
};
type Policy = { min_group_size: number; max_group_size: number };
type FieldErrors = Record<string, string>;
type ApiDetail = {
  code?: string;
  message?: string;
  field?: string;
  fields?: { path: string }[];
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
};
type PasswordResetDeliveryStatus = {
  development_mode: boolean;
  smtp_configured: boolean;
};
type DevelopmentResetLinkState = "idle" | "loading" | "ready" | "missing" | "error";
type PublicPage = "in" | "up" | "recover";
type StudentSignupMode = "group";
type PublicRoute = { page: PublicPage; signupRole: LoginRole | null; step: 1 | 2 | 3; studentMode: StudentSignupMode | null };
type DashboardPage = "account" | "admin-portal";

const STEPS = ["Academic Cycle", "Group Members", "Group Credentials"];
const configuredApi = (import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8010").replace(/\/$/, "");
const localBrowserHost = typeof window !== "undefined" ? window.location.hostname : "";
export const API = /:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(configuredApi) && localBrowserHost
  ? configuredApi.replace(/:\/\/(localhost|127\.0\.0\.1)/, `://${localBrowserHost}`)
  : configuredApi;
const INPUT =
  "w-full rounded-lg border border-[#DCE3ED] bg-white px-3.5 py-3 text-base text-[#243746] transition-colors focus:border-[#4663FF] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const PRIMARY =
  "rounded-lg bg-[#4663FF] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#354FE0] disabled:cursor-not-allowed disabled:bg-[#cddfd3] disabled:text-[#4f6470]";
const AUTH_PRIMARY =
  "rounded-xl bg-[#4663FF] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#354ee0] disabled:cursor-not-allowed disabled:bg-[#cddfd3] disabled:text-[#4f6470]";
const DEVELOPMENT_UNKNOWN_ACCOUNT_MESSAGE = "No account was found with this email address.";
const academicCycleError = (status: number) => ({ 401: "Your session has expired. Please sign in again.", 403: "You are not authorized to load academic cycles.", 404: "The academic-cycles endpoint was not found.", 500: "The backend could not load academic cycles." }[status] ?? "Academic cycles could not be loaded.");

const newMember = (): Member => ({
  id: crypto.randomUUID(),
  email: "",
  registration: "",
});
const registration = (value: string) => value.trim().toUpperCase();
const memberKey = (id: string, field: keyof Omit<Member, "id">) => `member.${id}.${field}`;
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
  if (!route || (route.page !== "in" && route.page !== "up" && route.page !== "recover") || (route.step !== 1 && route.step !== 2 && route.step !== 3)) return null;
  return publicRoute(route.page, "STUDENT", route.step, "group");
};

function Logo({ compact = false, auth = false, authMobile = false }: { compact?: boolean; auth?: boolean; authMobile?: boolean }) {
  const classes = compact
    ? { wrapper: "flex items-center gap-2", icon: "h-9 w-10 text-[#176B66]", wordmark: "text-xl font-bold tracking-tight" }
    : auth
      ? { wrapper: "flex items-center gap-3.5 sm:gap-4", icon: "h-auto w-[72px] text-[#c8f3df] lg:w-[100px]", wordmark: "text-[46px] font-bold tracking-tight text-white lg:text-[62px]" }
      : authMobile
        ? { wrapper: "flex items-center gap-3.5 sm:gap-4", icon: "h-auto w-[56px] text-[#176B66] sm:w-[72px]", wordmark: "text-[34px] font-bold tracking-tight sm:text-[46px]" }
        : { wrapper: "flex items-center gap-2.5", icon: "h-12 w-auto text-[#176B66]", wordmark: "text-[28px] font-bold tracking-tight sm:text-[32px]" };
  return (
    <div className={classes.wrapper}>
      <svg
        aria-hidden="true"
        className={classes.icon}
        viewBox="0 0 56 40"
        fill="none"
      >
        <path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor" />
        <path
          d="M15 20v8c5 5 21 5 26 0v-8M49 16v11"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle
          cx="49"
          cy="30"
          r="3"
          fill="#E4EEE7"
          stroke="currentColor"
          strokeWidth="2"
        />
      </svg>
      <span className={classes.wordmark}>FYPHub</span>
    </div>
  );
}

function AuthPhotoBackground() {
  return <div aria-hidden="true" className="auth-photo-background pointer-events-none absolute inset-0 overflow-hidden"><img src={signInStudentsImage} alt="" width="1200" height="800" className="h-full w-full object-cover object-[58%_center]" /><div className="absolute inset-0 bg-[linear-gradient(105deg,rgba(10,40,55,.82),rgba(11,70,78,.6)_55%,rgba(10,35,50,.5))]" /></div>;
}

function AuthLayout({ children, actions, compact = false }: { children: ReactNode; actions?: ReactNode; compact?: boolean }) {
  return <main className="relative min-h-screen overflow-x-hidden px-4 py-7 text-[#243746] sm:px-6 sm:py-10 lg:py-5"><AuthPhotoBackground /><div className="relative mx-auto grid max-w-[1280px] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(460px,500px)] lg:items-center lg:gap-16"><section className="hidden max-w-lg self-center text-white lg:block"><Logo auth /><h1 className="mt-14 text-4xl font-bold leading-[1.15] tracking-tight">From Your First Idea to Your Final Defense.</h1><p className="mt-5 max-w-[48ch] text-[17px] leading-[1.6] text-white/90">Bring your team, proposals, feedback, and progress together in one FYP workspace.</p><p className="mt-6 text-[15px] font-medium tracking-wide text-[#b9ddcf]">Stay focused. Build together.</p></section><div className={`auth-card mx-auto w-full max-w-[500px] rounded-3xl p-5 ${compact ? "sm:p-6" : "sm:p-7"}`}><header className={`mb-6 flex gap-4 ${actions ? "flex-col items-start sm:flex-row sm:items-center sm:justify-between" : "items-center justify-between lg:hidden"}`}><div className="lg:hidden"><Logo authMobile /></div>{actions && <div className="sm:ml-auto">{actions}</div>}</header>{children}</div></div></main>;
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  disabled,
  error,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "email";
  autoComplete?: string;
  disabled?: boolean;
  error?: string;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-sm font-semibold">
        {label}
      </label>
      <input
        id={id}
        type={type}
        value={value}
        autoComplete={autoComplete}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        className={`${INPUT} ${error ? "border-[#a43a33]" : ""}`}
        onChange={(event) => onChange(event.target.value)}
      />
      {error && (
        <p id={errorId} className="text-sm text-[#a43a33]">
          {error}
        </p>
      )}
    </div>
  );
}

function StepProgress({ step }: { step: number }) {
  return (
    <div className="mb-7">
      <div className="relative mx-auto max-w-[280px]">
        <div
          aria-hidden="true"
          className="absolute left-[16.666%] right-[16.666%] top-4 h-[2px] overflow-hidden bg-[#d8e2dc]"
        >
          <div
            className="h-full bg-[#176B66] transition-[width] duration-300 ease-in-out motion-reduce:transition-none"
            style={{ width: `${((step - 1) / 2) * 100}%` }}
          />
        </div>
        <ol
          aria-label="Registration progress"
          className="relative grid grid-cols-3"
        >
          {STEPS.map((label, index) => {
            const number = index + 1;
            const current = number === step;
            const completed = number < step;
            return (
              <li
                key={label}
                aria-current={current ? "step" : undefined}
                className="flex justify-center"
              >
                <span
                  aria-hidden="true"
                  className={[
                    "flex h-8 w-8 items-center justify-center rounded-full border text-xs font-bold transition-colors duration-300 motion-reduce:transition-none",
                    current
                      ? "border-[#176B66] bg-[#176B66] text-white"
                      : completed
                        ? "border-[#176B66] bg-[#E4EEE7] text-[#176B66]"
                        : "border-[#c5d1ca] bg-white text-[#64766d]",
                  ].join(" ")}
                >
                  {completed ? (
                    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
                      <path
                        d="m5 12 4 4 10-10"
                        stroke="currentColor"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    number
                  )}
                </span>
                <span className="sr-only">
                  Step {number}: {label}
                  {completed ? ", completed" : ""}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
      <h2 className="mt-5 text-center text-xl font-bold">{STEPS[step - 1]}</h2>
    </div>
  );
}

export default function App() {
  const [page, setPage] = useState<string>("in");
  const [authUser, setAuthUser] = useState<SafeUser | null>(null);
  const authUserRef = useRef<SafeUser | null>(null);
  useEffect(() => { authUserRef.current = authUser; }, [authUser]);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");
  const [step, setStep] = useState(1);
  const [notice, setNotice] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [login, setLogin] = useState({ email: "", password: "", confirm: "" });
  const [members, setMembers] = useState<Member[]>([]);
  const [signIn, setSignIn] = useState({ email: "", password: "" });
  const [recoveryView, setRecoveryView] = useState<"forgot" | "reset">(
    () => window.location.pathname === "/reset-password" ? "reset" : "forgot",
  );
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
    teamId: number;
    cycle: string;
  } | null>(null);
  const publicNavigationRef = useRef<(route: PublicRoute, mode?: "push" | "replace" | "pop") => void>(() => undefined);

  useEffect(() => {
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(`${API}/api/v1/academic-cycles`, {
          credentials: "include",
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(academicCycleError(response.status));
        const data: Cycle[] = await response.json();
        if (!controller.signal.aborted) {
          setCycles(data);
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
    if (window.location.pathname === "/reset-password") return;
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
        member.id === id ? { ...member, [field]: value } : member,
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
        const reg = registration(member.registration);
        const emailError = emailValidationMessage(member.email);
        if (emailError) next[`${prefix}.name`] = "Enter a valid member email address.";
        if (!reg)
          next[`${prefix}.registration`] = "Enter a registration number.";
        const normalizedEmail = normalizeEmail(member.email);
        if (normalizedEmail && emails.has(normalizedEmail)) {
          next[`${prefix}.name`] = "Member emails must be unique in this group.";
          next[emails.get(normalizedEmail)!] = "Member emails must be unique in this group.";
        }
        if (normalizedEmail) emails.set(normalizedEmail, `${prefix}.name`);
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
      const sharedEmailError = emailValidationMessage(login.email);
      if (sharedEmailError) next["login.email"] = "Enter a valid group email address.";
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
    setStep(next.step);
    setErrors(nextErrors);
    setNotice(Object.keys(nextErrors).length ? "Please correct the highlighted fields." : "");
    const current = readPublicRoute(window.history.state);
    const changed = !current || current.page !== next.page || current.signupRole !== next.signupRole || current.step !== next.step || current.studentMode !== next.studentMode;
    if (mode === "push" && changed) window.history.pushState({ fyphubNavigation: next }, "", window.location.href);
    if ((mode === "replace" || (mode === "pop" && changed)) && changed) window.history.replaceState({ fyphubNavigation: next }, "", window.location.href);
  }
  useEffect(() => {
    publicNavigationRef.current = navigatePublic;
  });
  useEffect(() => {
    const initial = readPublicRoute(window.history.state) ?? publicRoute("in");
    if (window.location.pathname === "/reset-password") {
      queueMicrotask(() => {
        setRecoveryView("reset");
        setResetToken(new URLSearchParams(window.location.search).get("token") ?? "");
        setPage("recover");
      });
      window.history.replaceState({ fyphubNavigation: publicRoute("recover") }, "", window.location.href);
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
      publicNavigationRef.current(readPublicRoute(event.state) ?? publicRoute("in"), "pop");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);
  function nextStep() {
    const next = validate(step);
    setErrors(next);
    if (Object.keys(next).length) {
      setNotice("Please correct the highlighted fields.");
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
      /^members\.(\d+)\.(email|registration_number)$/,
    );
    if (!match || !members[Number(match[1])]) return undefined;
    const field = {
      email: "email",
      registration_number: "registration",
    }[match[2]] as keyof Omit<Member, "id">;
    return memberKey(members[Number(match[1])].id, field);
  }
  function applyError(detail: ApiDetail) {
    const fields = [
      detail.field,
      ...(detail.fields?.map((item) => item.path) ?? []),
    ]
      .map(mapPath)
      .filter((value): value is string => Boolean(value));
    if (fields.length) {
      setErrors(
        Object.fromEntries(
          fields.map((field) => [field, detail.message ?? "Check this field."]),
        ),
      );
      setStep(Math.min(...fields.map(stepFor)));
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
      setNotice("Please correct the highlighted fields.");
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
        email: normalizeEmail(member.email),
        registration_number: registration(member.registration),
      })),
    };
    try {
      const response = await fetch(`${API}/api/v1/student/group-registration`, {
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
        teamId: data.team.id as number,
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
      setSignIn((current) => ({ ...current, password: "" }));
      window.history.pushState({ fyphubNavigation: { page: destination } }, "", window.location.href);
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
        setRecoveryError(body.detail?.code === "account_not_found" ? DEVELOPMENT_UNKNOWN_ACCOUNT_MESSAGE : "Password reset could not be requested.");
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
      navigatePublic(publicRoute("in"), "replace");
    }
  }

  const changePage = (value: "in" | "up") => {
    navigatePublic(publicRoute(value));
  };
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
                "Academic Cycles & Policies",
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
              Group ID: {success.teamId}. Academic cycle: {success.cycle}. Your group login is ready.
              {success.teamId}.
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
  if (page === "in")
    return (
      <AuthLayout compact>
          <div>
            <h1 className="text-[26px] font-bold sm:text-[28px]">Sign In</h1>
            <p className="mt-1.5 mb-4 text-sm text-[#4f6470]">
              Sign in to your FYP workspace.
            </p>
            <form
              className="mt-5 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                void performLogin();
              }}
            >
              <Field
                label="Group email"
                type="email"
                autoComplete="username"
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
                guidance
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
                  className="font-semibold text-[#176B66] underline"
                >
                  Forgot Password?
                </button>
              </div>
              {authError && (
                <p
                  role="alert"
                  className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]"
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
              <p className="text-center text-sm text-[#4f6470]">
                Don&apos;t have an account?{" "}
                <button
                  type="button"
                  onClick={() => navigatePublic(publicRoute("up"))}
                  className="font-semibold text-[#176B66] underline"
                >
                  Create Account
                </button>
              </p>
            </form>
          </div>
      </AuthLayout>
    );
  return (
    <AuthLayout actions={<nav aria-label="Account navigation" className="flex gap-1"><button type="button" aria-current={page === "in" ? "page" : undefined} disabled={submitting} onClick={() => changePage("in")} className={page === "in" ? "rounded-lg bg-[#E4EEE7] px-3 py-2 text-sm font-semibold text-[#176B66]" : "rounded-lg px-3 py-2 text-sm font-semibold text-[#4f6470] hover:text-[#176B66]"}>Sign In</button><button type="button" aria-current={page === "up" ? "page" : undefined} disabled={submitting} onClick={() => changePage("up")} className={page === "up" ? "rounded-lg bg-[#E4EEE7] px-3 py-2 text-sm font-semibold text-[#176B66]" : "rounded-lg px-3 py-2 text-sm font-semibold text-[#4f6470] hover:text-[#176B66]"}>Sign Up</button></nav>}>
          {page === "in" ? (
            <>
              <h1 className="mb-7 text-center text-2xl font-bold">Sign In</h1>
              <div className="space-y-5">
                <Field
                  label="Group email"
                  type="email"
                  autoComplete="username"
                  value={signIn.email}
                  onChange={(value) =>
                    setSignIn((current) => ({ ...current, email: value }))
                  }
                />
                <PasswordField
                  label="Password"
                  autoComplete="current-password"
                  guidance
                  value={signIn.password}
                  onChange={(value) =>
                    setSignIn((current) => ({ ...current, password: value }))
                  }
                />
                <button
                  type="button"
                  disabled
                  className="w-full cursor-not-allowed rounded-lg bg-[#cddfd3] py-3 text-sm font-semibold text-[#4f6470]"
                >
                  Sign In
                </button>
                <p className="text-center text-sm text-[#4f6470]">
                  Need a team account?{" "}
                  <button
                    type="button"
                    onClick={() => changePage("up")}
                    className="font-semibold text-[#176B66] underline"
                  >
                    Sign Up
                  </button>
                </p>
              </div>
            </>
          ) : success ? (
            <div className="space-y-5 py-5 text-center">
              <h1 className="text-2xl font-bold text-[#176B66]">
                Student group account created successfully.
              </h1>
              <p className="text-sm text-[#4f6470]">
                Group ID: {success.teamId}. Academic cycle: {success.cycle}.
              </p>
              <p className="text-sm text-[#4f6470]">
                Use the group email and password to sign in.
              </p>
            </div>
          ) : (
            <>
              <h1 className="text-center text-lg font-bold">
              Create Student Group Account
              </h1>
              <p className="mt-2 mb-6 text-center text-sm text-[#4f6470]">
                Your team will use one email and password.
              </p>
              <StepProgress step={step} />
              {step === 1 && (
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="sm:col-span-2 grid gap-2">
                    <label
                      htmlFor="academic-cycle"
                      className="text-sm font-semibold"
                    >
                      Academic cycle
                    </label>
                    <select
                      id="academic-cycle"
                      value={cycleId}
                      disabled={submitting || cyclesState === "loading"}
                      aria-invalid={Boolean(errors["account.cycle"])}
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
                          {cycle.display_name} ({cycle.academic_year ?? "Year"} {cycle.session ?? ""})
                          {cycle.registration_open ? " — open" : " — closed"}
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
                  <div className="flex flex-wrap items-center justify-between gap-3"><p className="text-sm text-[#4f6470]">{teamSize} of {maximum ?? "—"} members added</p><button type="button" disabled={submitting || !maximum || teamSize >= maximum} onClick={() => setMembers((current) => [...current, newMember()])} className="rounded-lg border border-[#176B66] px-3 py-2 text-sm font-semibold text-[#176B66] disabled:cursor-not-allowed disabled:border-[#cbd6d0] disabled:text-[#4f6470]">+ Add member</button></div>
                  {maximum && teamSize >= maximum && <p className="text-sm text-[#4f6470]">Maximum group size reached for this cycle.</p>}
                  {errors["members.configuration"] && <p role="alert" className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">{errors["members.configuration"]}</p>}
                  {members.map((member, index) => <article key={member.id} className="rounded-xl border border-[#dce4de] bg-[#f4f8f5] p-4"><div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-bold">Member {index + 1}</h3><button type="button" disabled={submitting || members.length <= minimum} aria-label={`Remove Member ${index + 1}`} onClick={() => setMembers((current) => current.filter((item) => item.id !== member.id))} className="text-xs font-semibold text-[#176B66] underline disabled:text-[#4f6470]">Remove</button></div><div className="grid gap-4 sm:grid-cols-2"><Field label="Member email" type="email" value={member.email} disabled={submitting} error={errors[memberKey(member.id, "email")]} onChange={(value) => updateMember(member.id, "email", value)} /><Field label="Registration number" value={member.registration} disabled={submitting} error={errors[memberKey(member.id, "registration")]} onChange={(value) => updateMember(member.id, "registration", value)} /></div></article>)}
                </div>
              )}
              {step === 3 && (
                <div className="space-y-4">
                  <Field label="Group email" type="email" autoComplete="username" value={login.email} disabled={submitting} error={errors["login.email"]} onChange={(value) => updateLogin("email", value)} />
                  <PasswordField label="Password" value={login.password} disabled={submitting} error={errors["login.password"]} onChange={(value) => updateLogin("password", value)} />
                  <PasswordField label="Confirm password" value={login.confirm} disabled={submitting} error={errors["login.confirm"]} onChange={(value) => updateLogin("confirm", value)} />
                </div>
              )}
              {notice && (
                <p
                  role="alert"
                  className="mt-5 rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]"
                >
                  {notice}
                </p>
              )}
              <div className="mt-7 flex items-center justify-between gap-3 border-t border-[#e8ede9] pt-5">
                {step > 1 && (
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={() => window.history.back()}
                    className="rounded-lg border border-[#cbd6d0] px-5 py-2.5 text-sm font-semibold disabled:cursor-not-allowed"
                  >
                    Back
                  </button>
                )}
                {step < 3 ? (
                  <button
                    type="button"
                    disabled={submitting}
                    onClick={nextStep}
                    className={`${AUTH_PRIMARY} ml-auto`}
                  >
                    Next →
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={submitting || !canSubmit}
                    onClick={() => void submit()}
                    className={`${AUTH_PRIMARY} ml-auto`}
                  >
                    {submitting ? "Creating..." : "Create Student Group Account"}
                  </button>
                )}
              </div>
            </>
          )}
    </AuthLayout>
  );
}
