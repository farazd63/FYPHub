import { StudentMatching } from "./StudentMatching";
import { InviteeResponse } from "./Invitations";
import { JoinRequestForm } from "./JoinRequests";
import { GroupChannels } from "./GroupChannels";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { AdminPortal } from "./AdminPortal";
import { PasswordField } from "./PasswordField";
import signInStudentsImage from "./assets/sign-in-students.webp";

type Member = { id: string; name: string; registration: string; email: string };
type Details = { name: string; registration: string; email: string };
type Cycle = {
  id: number;
  code: string;
  display_name: string;
  registration_open: boolean;
};
type Policy = { max_group_size: number };
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
};
type PublicPage = "in" | "up" | "recover";
type PublicRoute = { page: PublicPage; signupRole: LoginRole | null; step: 1 | 2 | 3 };

const STEPS = ["Account Details", "Login Details", "Team Members"];
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const API = (
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8010"
).replace(/\/$/, "");
const INPUT =
  "w-full rounded-lg border border-[#DCE3ED] bg-white px-3.5 py-3 text-base text-[#243746] transition-colors focus:border-[#4663FF] disabled:cursor-not-allowed disabled:bg-[#f4f6f4]";
const PRIMARY =
  "rounded-lg bg-[#4663FF] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#354FE0] disabled:cursor-not-allowed disabled:bg-[#cddfd3] disabled:text-[#4f6470]";
const AUTH_PRIMARY =
  "rounded-xl bg-[#4663FF] px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[#354ee0] disabled:cursor-not-allowed disabled:bg-[#cddfd3] disabled:text-[#4f6470]";

const newMember = (): Member => ({
  id: crypto.randomUUID(),
  name: "",
  registration: "",
  email: "",
});
const registration = (value: string) => value.trim().toUpperCase();
const email = (value: string) => value.trim().toLowerCase();
const memberKey = (id: string, field: keyof Details) => `member.${id}.${field}`;
const isLoginRole = (value: unknown): value is LoginRole => typeof value === "string" && ["STUDENT", "SUPERVISOR", "PANEL_MEMBER", "COORDINATOR", "ADMIN"].includes(value);
const publicRoute = (page: PublicPage, signupRole: LoginRole | null = null, step: 1 | 2 | 3 = 1): PublicRoute => ({ page, signupRole: page === "up" ? signupRole : null, step: page === "up" && signupRole === "STUDENT" ? step : 1 });
const readPublicRoute = (value: unknown): PublicRoute | null => {
  const route = (value as { fyphubNavigation?: unknown } | null)?.fyphubNavigation as Partial<PublicRoute> | undefined;
  if (!route || (route.page !== "in" && route.page !== "up" && route.page !== "recover") || (route.signupRole !== null && !isLoginRole(route.signupRole)) || (route.step !== 1 && route.step !== 2 && route.step !== 3)) return null;
  return publicRoute(route.page, route.signupRole, route.step);
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

const ROLES: { value: LoginRole; label: string }[] = [
  { value: "STUDENT", label: "Student" },
  { value: "SUPERVISOR", label: "Supervisor" },
  { value: "PANEL_MEMBER", label: "Evaluator" },
  { value: "COORDINATOR", label: "Coordinator" },
  { value: "ADMIN", label: "Administrator" },
];

function RoleIcon({ role }: { role: LoginRole }) {
  const paths =
    role === "STUDENT"
      ? ["M3 10 12 5l9 5-9 5-9-5Z", "M6 12v4c2 2 10 2 12 0v-4", "M21 10v5"]
      : role === "SUPERVISOR"
        ? [
            "M8 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z",
            "M3 20c0-3 2-5 5-5s5 2 5 5",
            "M14 6h7v13h-7zM16 10h3M16 13h3",
          ]
        : role === "COORDINATOR"
          ? [
              "M5 5h4v4H5zM15 5h4v4h-4zM10 16h4v4h-4z",
              "M9 7h6M17 9v4l-5 3M7 9v4l5 3",
            ]
          : role === "PANEL_MEMBER"
            ? ["M7 3h10v18H7zM10 3v3h4V3", "M10 12l2 2 4-4"]
            : [
                "M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6l7-3Z",
                "M12 9v6m-3-3h6",
                "M18 15l1 1m0-3-1 1",
              ];
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      className="h-5 w-5"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {paths.map((d) => (
        <path key={d} d={d} />
      ))}
    </svg>
  );
}

function AuthPhotoBackground() {
  return <div aria-hidden="true" className="auth-photo-background pointer-events-none absolute inset-0 overflow-hidden"><img src={signInStudentsImage} alt="" width="1200" height="800" className="h-full w-full object-cover object-[58%_center]" /><div className="absolute inset-0 bg-[linear-gradient(105deg,rgba(10,40,55,.82),rgba(11,70,78,.6)_55%,rgba(10,35,50,.5))]" /></div>;
}

function AuthLayout({ children, actions, compact = false }: { children: ReactNode; actions?: ReactNode; compact?: boolean }) {
  return <main className="relative min-h-screen overflow-x-hidden px-4 py-7 text-[#243746] sm:px-6 sm:py-10 lg:py-5"><AuthPhotoBackground /><div className="relative mx-auto grid max-w-[1280px] gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(460px,500px)] lg:items-center lg:gap-16"><section className="hidden max-w-lg self-center text-white lg:block"><Logo auth /><h1 className="mt-14 text-4xl font-bold leading-[1.15] tracking-tight">From Your First Idea to Your Final Defense.</h1><p className="mt-5 max-w-[48ch] text-[17px] leading-[1.6] text-white/90">Bring your team, proposals, feedback, and progress together in one FYP workspace.</p><p className="mt-6 text-[15px] font-medium tracking-wide text-[#b9ddcf]">Stay focused. Build together.</p></section><div className={`auth-card mx-auto w-full max-w-[500px] rounded-3xl p-5 ${compact ? "sm:p-6" : "sm:p-7"}`}><header className={`mb-6 flex gap-4 ${actions ? "flex-col items-start sm:flex-row sm:items-center sm:justify-between" : "items-center justify-between lg:hidden"}`}><div className="lg:hidden"><Logo authMobile /></div>{actions && <div className="sm:ml-auto">{actions}</div>}</header>{children}</div></div></main>;
}

function RoleCards({
  value,
  onChange,
  disabled = false,
  includeAdmin = false,
  compact = false,
}: {
  value: LoginRole;
  onChange: (role: LoginRole) => void;
  disabled?: boolean;
  includeAdmin?: boolean;
  compact?: boolean;
}) {
  const roles = includeAdmin ? ROLES : ROLES;
  return (
    <div
      className={`grid grid-cols-2 ${compact ? "gap-[10px]" : "gap-3"}`}
      role="radiogroup"
      aria-label="Account type"
    >
      {roles.map((role) => (
        <button
          key={role.value}
          type="button"
          role="radio"
          aria-checked={value === role.value}
          disabled={disabled}
          onClick={() => onChange(role.value)}
          className={`flex ${compact ? "min-h-[54px]" : "min-h-[64px]"} items-center gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${value === role.value ? "border-[#4663FF] bg-[#eef0ff] ring-1 ring-[#4663FF]" : "border-[#dce4de] bg-white/75 hover:border-[#8b9aff]"}`}
        >
          <span className="block shrink-0 text-[#4663FF]">
            <RoleIcon role={role.value} />
          </span>
          <span className="text-sm font-bold">{role.label}</span>
        </button>
      ))}
    </div>
  );
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
  const [loginRole, setLoginRole] = useState<LoginRole>("STUDENT");
  const [signupRole, setSignupRole] = useState<LoginRole | null>(null);
  const [authUser, setAuthUser] = useState<SafeUser | null>(null);
  const authUserRef = useRef<SafeUser | null>(null);
  useEffect(() => { authUserRef.current = authUser; }, [authUser]);
  const [authSubmitting, setAuthSubmitting] = useState(false);
  const [authError, setAuthError] = useState("");
  const [step, setStep] = useState(1);
  const [notice, setNotice] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [account, setAccount] = useState<Details>({
    name: "",
    registration: "",
    email: "",
  });
  const [login, setLogin] = useState({ email: "", password: "", confirm: "" });
  const [members, setMembers] = useState<Member[]>(() => [
    newMember(),
    newMember(),
  ]);
  const [signIn, setSignIn] = useState({ email: "", password: "" });
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
          signal: controller.signal,
        });
        if (!response.ok) throw new Error();
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
          { signal: controller.signal },
        );
        if (response.status === 404) {
          if (!controller.signal.aborted) setPolicyState("unavailable");
          return;
        }
        if (!response.ok) throw new Error();
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
    void (async () => {
      try {
        const response = await fetch(`${API}/api/v1/auth/me`, {
          credentials: "include",
        });
        if (response.ok) {
          setAuthUser((await response.json()) as SafeUser);
          setPage("account");
        }
      } catch {
        /* A local API may not be running while the public signup form is used. */
      }
    })();
  }, []);
  useEffect(() => {
    if (authUser?.role !== "ADMIN") return;
    void (async () => {
      try {
        const response = await fetch(`${API}/api/v1/admin/me`, {
          credentials: "include",
        });
        if (response.ok) setPage("admin-portal");
        else {
          setAuthUser(null);
          setPage("in");
          setAuthError(
            "Administrator access is not available for this account.",
          );
        }
      } catch {
        setAuthError("Administrator access could not be verified.");
      }
    })();
  }, [authUser]);

  const selectedCycle = cycles.find((cycle) => String(cycle.id) === cycleId);
  const maximum = policy?.max_group_size;
  const teamSize = members.length + 1;
  const clear = (key: string) => {
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setNotice("");
  };
  const updateAccount = (field: keyof Details, value: string) => {
    setAccount((current) => ({ ...current, [field]: value }));
    clear(`account.${field}`);
  };
  const updateLogin = (field: keyof typeof login, value: string) => {
    setLogin((current) => ({ ...current, [field]: value }));
    clear(`login.${field}`);
  };
  const updateMember = (id: string, field: keyof Details, value: string) => {
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
      if (!account.name.trim())
        next["account.name"] = "Enter the creator's full name.";
      if (!registration(account.registration))
        next["account.registration"] =
          "Enter the creator's registration number.";
      if (!EMAIL.test(email(account.email)))
        next["account.email"] = "Enter a valid university email.";
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
      if (!EMAIL.test(email(login.email)))
        next["login.email"] = "Enter a valid shared login email.";
      if (login.password.length < 8 || login.password.length > 128)
        next["login.password"] =
          login.password.length < 8
            ? "Use at least 8 characters."
            : "Password must be no more than 128 characters.";
      if (login.password !== login.confirm)
        next["login.confirm"] = "Passwords do not match.";
    }
    if (target === 3 || target === 0) {
      const registrations = new Map<string, string>();
      const emails = new Map<string, string>();
      [{ id: "creator", ...account }, ...members].forEach((member) => {
        const prefix =
          member.id === "creator" ? "account" : `member.${member.id}`;
        const reg = registration(member.registration);
        const address = email(member.email);
        if (!member.name.trim()) next[`${prefix}.name`] = "Enter a full name.";
        if (!reg)
          next[`${prefix}.registration`] = "Enter a registration number.";
        if (!EMAIL.test(address))
          next[`${prefix}.email`] = "Enter a valid university email.";
        if (reg && registrations.has(reg)) {
          next[`${prefix}.registration`] =
            "Registration number is already used in this team.";
          next[registrations.get(reg)!] =
            "Registration number is already used in this team.";
        }
        if (address && emails.has(address)) {
          next[`${prefix}.email`] =
            "University email is already used in this team.";
          next[emails.get(address)!] =
            "University email is already used in this team.";
        }
        if (reg) registrations.set(reg, `${prefix}.registration`);
        if (address) emails.set(address, `${prefix}.email`);
      });
      if (!maximum)
        next["members.configuration"] =
          "Choose a cycle with an available group policy.";
      if (maximum && teamSize > maximum)
        next["members.configuration"] =
          `This team has ${teamSize} members; the selected cycle allows ${maximum}. Remove members before submitting.`;
    }
    return next;
  }
  const stepFor = (key?: string) =>
    !key || key.startsWith("member") || key.startsWith("members")
      ? 3
      : key.startsWith("login")
        ? 2
        : 1;
  function navigatePublic(route: PublicRoute, mode: "push" | "replace" | "pop" = "push") {
    let next = publicRoute(route.page, route.signupRole, route.step);
    let nextErrors: FieldErrors = {};
    if (next.page === "up" && next.signupRole === "STUDENT" && next.step > 1) {
      nextErrors = validate(1);
      if (!Object.keys(nextErrors).length && next.step > 2) nextErrors = validate(2);
      if (Object.keys(nextErrors).length) {
        next = publicRoute("up", "STUDENT", Math.min(...Object.keys(nextErrors).map(stepFor)) as 1 | 2 | 3);
      }
    }
    setPage(next.page);
    setSignupRole(next.signupRole);
    setStep(next.step);
    setErrors(nextErrors);
    setNotice(Object.keys(nextErrors).length ? "Please correct the highlighted fields." : "");
    const current = readPublicRoute(window.history.state);
    const changed = !current || current.page !== next.page || current.signupRole !== next.signupRole || current.step !== next.step;
    if (mode === "push" && changed) window.history.pushState({ fyphubNavigation: next }, "", window.location.href);
    if ((mode === "replace" || (mode === "pop" && changed)) && changed) window.history.replaceState({ fyphubNavigation: next }, "", window.location.href);
  }
  useEffect(() => {
    publicNavigationRef.current = navigatePublic;
  });
  useEffect(() => {
    const initial = readPublicRoute(window.history.state) ?? publicRoute("in");
    if (!readPublicRoute(window.history.state)) window.history.replaceState({ fyphubNavigation: initial }, "", window.location.href);
    publicNavigationRef.current(initial, "pop");
    const onPopState = (event: PopStateEvent) => {
      const destination = (event.state as { fyphubNavigation?: { page?: string } } | null)?.fyphubNavigation?.page;
      if (destination === "admin-portal" && authUserRef.current?.role === "ADMIN") {
        void fetch(`${API}/api/v1/admin/me`, { credentials: "include" }).then(async response => {
          if (!response.ok) {
            setAuthUser(null);
            publicNavigationRef.current(publicRoute("in"), "pop");
            return;
          }
          setAuthUser((await response.json()) as SafeUser);
          setPage("admin-portal");
        }).catch(() => {
          setAuthUser(null);
          publicNavigationRef.current(publicRoute("in"), "pop");
        });
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
    navigatePublic(publicRoute("up", "STUDENT", Math.min(3, step + 1) as 1 | 2 | 3));
  }
  function mapPath(path?: string) {
    if (!path) return undefined;
    const basic: Record<string, string> = {
      "creator.full_name": "account.name",
      "creator.registration_number": "account.registration",
      "creator.university_email": "account.email",
      shared_login_email: "login.email",
      password: "login.password",
      academic_cycle_id: "account.cycle",
      members: "members.configuration",
    };
    if (basic[path]) return basic[path];
    const match = path.match(
      /^members\.(\d+)\.(full_name|registration_number|university_email)$/,
    );
    if (!match || !members[Number(match[1])]) return undefined;
    const field = {
      full_name: "name",
      registration_number: "registration",
      university_email: "email",
    }[match[2]] as keyof Details;
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
    setNotice(detail.message ?? "Team account could not be created.");
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
      creator: {
        full_name: account.name.trim(),
        registration_number: registration(account.registration),
        university_email: email(account.email),
      },
      shared_login_email: email(login.email),
      password: login.password,
      members: members.map((member) => ({
        full_name: member.name.trim(),
        registration_number: registration(member.registration),
        university_email: email(member.email),
      })),
    };
    try {
      const response = await fetch(`${API}/api/v1/team-registration`, {
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
        "Enter your registered email or creator registration number and password.",
      );
      return;
    }
    setAuthSubmitting(true);
    setAuthError("");
    const payload: Record<string, string> = {
      password: signIn.password,
      requested_role: loginRole,
    };
    if (EMAIL.test(identifier)) payload.email = identifier;
    else payload.registration_number = identifier;
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
            ? "The selected account type or credentials are incorrect."
            : "Sign in could not be completed. Please check your details.",
        );
        return;
      }
      const user = (await response.json()) as SafeUser;
      setAuthUser(user);
      setSignIn((current) => ({ ...current, password: "" }));
      const destination = user.role === "ADMIN" ? "admin-portal" : "account";
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
  if (page === "account" && authUser)
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
          {(authUser.role === "STUDENT" || authUser.role === "SUPERVISOR") && <GroupChannels api={API} role={authUser.role} />}
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
            <p className="mb-3 text-xs font-bold uppercase tracking-wide text-[#4f6470]">
              Administration
            </p>
            <nav aria-label="Admin navigation" className="grid gap-1">
              {[
                "Overview",
                "Users & Roles",
                "Academic Cycles & Policies",
                "Proposal Templates",
                "Supervisor Capacity",
                "Evaluation Rubrics",
                "Deadlines",
                "Reminders & Escalations",
                "Audit History",
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
            <p className="text-sm font-semibold text-[#3984E8]">
              Administrator portal
            </p>
            <h1 className="mt-1 text-2xl font-bold">Overview</h1>
            <p className="mt-3 max-w-xl text-sm text-[#4f6470]">
              Your administrator session is verified. Management data and
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
  if (page === "admin-portal" && authUser)
    return (
      <AdminPortal api={API} user={authUser} onLogout={() => void signOut()} />
    );
  if (page === "recover")
    return (
      <AuthLayout>
          <div>
            <h1 className="text-2xl font-bold">Reset your password</h1>
            <p className="mt-2 text-sm text-[#4f6470]">
              Password recovery email delivery is not configured for this
              project.
            </p>
            <Field
              label="Registered email"
              type="email"
              value=""
              onChange={() => undefined}
              disabled
            />
            <p className="mt-4 text-sm text-[#4f6470]">
              Contact your FYP coordinator for account recovery.
            </p>
            <button
              type="button"
              onClick={() => navigatePublic(publicRoute("in"))}
              className="mt-6 text-sm font-semibold text-[#176B66] underline"
            >
              Back to Login
            </button>
          </div>
      </AuthLayout>
    );
  if (page === "up" && success)
    return (
      <AuthLayout>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-[#176B66]">
              Team account created
            </h1>
            <p className="mt-3 text-sm text-[#4f6470]">
              Your shared team account for {success.cycle} was created. Team ID:{" "}
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
  if (page === "up" && signupRole === null)
    return (
      <AuthLayout>
          <div>
            <h1 className="text-2xl font-bold">Create Your Account</h1>
            <p className="mt-2 mb-6 text-sm text-[#4f6470]">
              Join the FYP Intelligence Hub.
            </p>
            <RoleCards value="STUDENT" onChange={(role) => navigatePublic(publicRoute("up", role, 1))} />
            <p className="mt-6 text-center text-sm text-[#4f6470]">
              Already have an account?{" "}
              <button
                type="button"
                onClick={() => navigatePublic(publicRoute("in"))}
                className="font-semibold text-[#176B66] underline"
              >
                Login
              </button>
            </p>
          </div>
      </AuthLayout>
    );
  if (page === "up" && signupRole !== "STUDENT")
    return (
      <AuthLayout>
          <div>
            <h1 className="text-2xl font-bold">Restricted registration</h1>
            <p className="mt-3 text-sm text-[#4f6470]">
              {ROLES.find((role) => role.value === signupRole)?.label} accounts
              are created through an authorized invitation or administrator
              approval.
            </p>
            <button
              type="button"
              onClick={() => navigatePublic(publicRoute("up"))}
              className={`${AUTH_PRIMARY} mt-6 w-full`}
            >
              Choose another account type
            </button>
            <button
              type="button"
              onClick={() => navigatePublic(publicRoute("in"))}
              className="mt-4 w-full text-sm font-semibold text-[#176B66] underline"
            >
              Back to Login
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
            <RoleCards
              value={loginRole}
              onChange={setLoginRole}
              disabled={authSubmitting}
              compact
            />
            <div className="mt-4 space-y-3">
              <Field
                label="Email or Registration ID"
                autoComplete="username"
                value={signIn.email}
                disabled={authSubmitting}
                onChange={(value) => {
                  setSignIn((current) => ({ ...current, email: value }));
                  setAuthError("");
                }}
              />
              <PasswordField
                label="Password"
                autoComplete="current-password"
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
                  onClick={() => navigatePublic(publicRoute("recover"))}
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
                type="button"
                disabled={authSubmitting}
                onClick={() => void performLogin()}
                className={`${AUTH_PRIMARY} min-h-[46px] w-full`}
              >
                {authSubmitting ? "Signing in..." : "Login"}
              </button>
              <StudentMatching api={API} />
              <JoinRequestForm api={API} />
              <InviteeResponse api={API} />
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
            </div>
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
                  label="Shared login email"
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
                Team account created
              </h1>
              <p className="text-sm text-[#4f6470]">
                Your shared team account for {success.cycle} was created. Team
                ID: {success.teamId}.
              </p>
              <p className="text-sm text-[#4f6470]">
                Sign In will be available when authentication is implemented.
              </p>
            </div>
          ) : (
            <>
              <h1 className="text-center text-lg font-bold">
                Create Team Account
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
                          {cycle.display_name} ({cycle.code})
                          {cycle.registration_open ? "" : " â€” closed"}
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
                        This cycle allows up to {maximum} members, including the
                        creator.
                      </p>
                    )}
                  </div>
                  <div className="sm:col-span-2">
                    <Field
                      label="Full name"
                      autoComplete="name"
                      value={account.name}
                      disabled={submitting}
                      error={errors["account.name"]}
                      onChange={(value) => updateAccount("name", value)}
                    />
                  </div>
                  <Field
                    label="Registration number"
                    value={account.registration}
                    disabled={submitting}
                    error={errors["account.registration"]}
                    onChange={(value) => updateAccount("registration", value)}
                  />
                  <Field
                    label="University email"
                    type="email"
                    value={account.email}
                    disabled={submitting}
                    error={errors["account.email"]}
                    onChange={(value) => updateAccount("email", value)}
                  />
                </div>
              )}
              {step === 2 && (
                <div className="grid gap-5 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <Field
                      label="Shared login email"
                      type="email"
                      autoComplete="username"
                      value={login.email}
                      disabled={submitting}
                      error={errors["login.email"]}
                      onChange={(value) => updateLogin("email", value)}
                    />
                  </div>
                  <PasswordField
                    label="Password"
                    value={login.password}
                    disabled={submitting}
                    error={errors["login.password"]}
                    onChange={(value) => updateLogin("password", value)}
                  />
                  <PasswordField
                    label="Confirm password"
                    value={login.confirm}
                    disabled={submitting}
                    error={errors["login.confirm"]}
                    onChange={(value) => updateLogin("confirm", value)}
                  />
                </div>
              )}
              {step === 3 && (
                <div className="space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-sm text-[#4f6470]">
                      Creator is Member 1.{" "}
                      {maximum
                        ? `${teamSize} of ${maximum} members.`
                        : "Choose a cycle to see the team limit."}
                    </p>
                    <button
                      type="button"
                      disabled={submitting || !maximum || teamSize >= maximum}
                      onClick={() =>
                        setMembers((current) => [...current, newMember()])
                      }
                      className="rounded-lg border border-[#176B66] px-3 py-2 text-sm font-semibold text-[#176B66] disabled:cursor-not-allowed disabled:border-[#cbd6d0] disabled:text-[#4f6470]"
                    >
                      + Add Member
                    </button>
                  </div>
                  {errors["members.configuration"] && (
                    <p className="rounded-lg bg-[#fff3f0] px-3 py-2 text-sm text-[#a43a33]">
                      {errors["members.configuration"]}
                    </p>
                  )}
                  {members.map((member, index) => (
                    <article
                      key={member.id}
                      className="rounded-xl border border-[#dce4de] bg-[#f4f8f5] p-4"
                    >
                      <div className="mb-4 flex items-center justify-between">
                        <h3 className="text-sm font-bold">
                          Member {index + 2}
                        </h3>
                        <button
                          type="button"
                          disabled={submitting}
                          aria-label={`Remove Member ${index + 2}`}
                          onClick={() =>
                            setMembers((current) =>
                              current.filter((item) => item.id !== member.id),
                            )
                          }
                          className="text-xs font-semibold text-[#176B66] underline disabled:text-[#4f6470]"
                        >
                          Remove
                        </button>
                      </div>
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div className="sm:col-span-2">
                          <Field
                            label="Full name"
                            value={member.name}
                            disabled={submitting}
                            error={errors[memberKey(member.id, "name")]}
                            onChange={(value) =>
                              updateMember(member.id, "name", value)
                            }
                          />
                        </div>
                        <Field
                          label="Registration number"
                          value={member.registration}
                          disabled={submitting}
                          error={errors[memberKey(member.id, "registration")]}
                          onChange={(value) =>
                            updateMember(member.id, "registration", value)
                          }
                        />
                        <Field
                          label="University email"
                          type="email"
                          value={member.email}
                          disabled={submitting}
                          error={errors[memberKey(member.id, "email")]}
                          onChange={(value) =>
                            updateMember(member.id, "email", value)
                          }
                        />
                      </div>
                    </article>
                  ))}
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
                    Next â†’
                  </button>
                ) : (
                  <button
                    type="button"
                    disabled={submitting || !canSubmit}
                    onClick={() => void submit()}
                    className={`${AUTH_PRIMARY} ml-auto`}
                  >
                    {submitting ? "Creating..." : "Create Team Account"}
                  </button>
                )}
              </div>
            </>
          )}
    </AuthLayout>
  );
}

