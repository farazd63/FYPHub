import { useCallback, useEffect, useState } from "react";
import { KeyRound, Pencil, Power, ShieldCheck, ShieldOff, Trash2 } from "lucide-react";
import { PasswordField } from "./PasswordField";
import { passwordPolicyError } from "./passwordPolicy";
import { emailValidationMessage, normalizeEmail } from "./emailValidation";
import { AdminAddButton } from "./ui/AdminAddButton";
import { IconButton } from "./ui/IconButton";
import { ModalPortal } from "./ui/ModalPortal";

type Role = "STUDENT" | "SUPERVISOR" | "COORDINATOR" | "PANEL_MEMBER" | "ADMIN";
type User = {
  id: number;
  full_name: string;
  group_name?: string | null;
  email: string;
  registration_number: string | null;
  role: Role;
  roles?: Role[];
  is_active: boolean;
  coordinator_academic_cycle_ids?: number[];
  coordinator_academic_cycle_names?: string[];
  // Fallback fields for responses from older backend instances.
  coordinator_academic_cycle_id?: number | null;
  coordinator_academic_cycle_name?: string | null;
};
type AcademicCycle = {
  id: number;
  code: string;
  display_name: string;
  registration_open: boolean;
  coordinator_id?: number | null;
};
type Page = { items: User[]; page: number; page_size: number; total: number };
const roles: Role[] = [
  "STUDENT",
  "SUPERVISOR",
  "COORDINATOR",
  "PANEL_MEMBER",
  "ADMIN",
];
const roleLabel: Record<Role, string> = {
  STUDENT: "Group",
  SUPERVISOR: "Supervisor",
  COORDINATOR: "Coordinator",
  PANEL_MEMBER: "Evaluator",
  ADMIN: "Administrator",
};
const input =
  "w-full rounded-lg border border-[#cbd6d0] bg-white px-3 py-2 text-sm text-[#243746] focus:border-[#176b66]";
const detail = (value: unknown) =>
  (value as { detail?: { message?: string } })?.detail?.message ??
  "The account change could not be completed.";
const accountLabel = (user: User) =>
  user.role === "STUDENT" ? user.group_name || "Student group" : user.full_name;
const roleBadgeClass =
  "inline-flex items-center rounded-full border border-[#c7d5f5] bg-gradient-to-r from-[#eef5ff] to-[#eeedff] px-2.5 py-1 text-xs font-bold text-[#344f9b]";
const coordinatorCycleIds = (user: User) => user.coordinator_academic_cycle_ids?.length
  ? user.coordinator_academic_cycle_ids
  : user.coordinator_academic_cycle_id == null ? [] : [user.coordinator_academic_cycle_id];
const coordinatorCycleNames = (user: User) => user.coordinator_academic_cycle_names?.length
  ? user.coordinator_academic_cycle_names
  : user.coordinator_academic_cycle_name ? [user.coordinator_academic_cycle_name] : [];
const selectedRoles = (user: User): Role[] => user.roles?.length ? user.roles : [user.role];

function RolePicker({ selected, allowed, onChange }: { selected: Role[]; allowed: Role[]; onChange: (roles: Role[]) => void }) {
  return (
    <div className="grid gap-2 rounded-lg border border-[#cbd6d0] bg-[#f8fbfa] p-2">
      {allowed.map((role) => {
        const checked = selected.includes(role);
        return (
          <label key={role} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm transition ${checked ? "border-[#176b66] bg-[#e6f3f0] text-[#123f3d]" : "border-transparent bg-white text-[#243746] hover:border-[#b8ccc7]"}`}>
            <input
              type="checkbox"
              checked={checked}
              onChange={() => {
                if (checked && selected.length === 1) return;
                onChange(checked ? selected.filter((item) => item !== role) : [...selected, role]);
              }}
              className="h-4 w-4 accent-[#176b66]"
            />
            <span>{roleLabel[role]}</span>
          </label>
        );
      })}
    </div>
  );
}

function CoordinatorCyclePicker({
  cycles,
  selectedIds,
  onChange,
}: {
  cycles: AcademicCycle[];
  selectedIds: string[];
  onChange: (ids: string[]) => void;
}) {
  return (
    <div className="grid gap-2 rounded-lg border border-[#cbd6d0] bg-[#f8fbfa] p-2">
      {cycles.length ? cycles.map((cycle) => {
        const cycleId = String(cycle.id);
        const selected = selectedIds.includes(cycleId);
        return (
          <label
            key={cycle.id}
            className={`flex cursor-pointer items-center gap-3 rounded-md border px-3 py-2 text-sm transition ${selected ? "border-[#176b66] bg-[#e6f3f0] text-[#123f3d]" : "border-transparent bg-white text-[#243746] hover:border-[#b8ccc7]"}`}
          >
            <input
              type="checkbox"
              checked={selected}
              onChange={() => onChange(selected ? selectedIds.filter((id) => id !== cycleId) : [...selectedIds, cycleId])}
              className="h-4 w-4 accent-[#176b66]"
            />
            <span className="min-w-0">
              <span className="block font-semibold">{cycle.display_name}</span>
              <span className="block text-xs font-normal text-[#60716b]">
                {cycle.code}{!cycle.registration_open ? " — current assignment" : ""}
              </span>
            </span>
          </label>
        );
      }) : (
        <p className="px-2 py-1 text-sm font-normal text-[#60716b]">No eligible academic cycles are available.</p>
      )}
    </div>
  );
}

export function AdminUsersRoles({ api }: { api: string }) {
  const [data, setData] = useState<Page>({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
  });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [search, setSearch] = useState(() => new URLSearchParams(window.location.search).get("search")?.trim() ?? "");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("true");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [passwordUser, setPasswordUser] = useState<User | null>(null);
  const [passwordForm, setPasswordForm] = useState({ new_password: "", confirm_password: "" });
  const [passwordError, setPasswordError] = useState("");
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ full_name: "", email: "", registration_number: "", roles: ["SUPERVISOR"] as Role[], coordinator_academic_cycle_ids: [] as string[] });
  const [editError, setEditError] = useState("");
  const [academicCycles, setAcademicCycles] = useState<AcademicCycle[]>([]);
  const [confirm, setConfirm] = useState<{
    user: User;
    type: "status" | "delete";
    value: string;
  } | null>(null);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    roles: ["SUPERVISOR"] as Role[],
    registration_number: "",
    coordinator_academic_cycle_ids: [] as string[],
  });
  const [fieldError, setFieldError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const availableCoordinatorCycles = academicCycles.filter((cycle) =>
    cycle.registration_open && !cycle.coordinator_id,
  );
  const editCycleIds = new Set(editForm.coordinator_academic_cycle_ids.map(Number));
  const editCoordinatorCycles = academicCycles.filter((cycle) =>
    (cycle.registration_open && (!cycle.coordinator_id || cycle.coordinator_id === editUser?.id)) || editCycleIds.has(cycle.id),
  );
  const emailError = emailTouched && form.email.trim()
    ? emailValidationMessage(form.email)
    : undefined;
  const load = useCallback(async () => {
    setState("loading");
    const query = new URLSearchParams({ page: String(page), page_size: "20" });
    if (search.trim()) query.set("search", search.trim());
    if (role) query.set("role", role);
    if (status) query.set("is_active", status);
    try {
      const response = await fetch(`${api}/api/v1/admin/users?${query}`, {
        credentials: "include",
      });
      if (!response.ok) throw new Error();
      setData((await response.json()) as Page);
      setState("ready");
    } catch {
      setState("error");
    }
  }, [api, page, role, search, status]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      void load();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);
  useEffect(() => {
    let cancelled = false;
    void fetch(`${api}/api/v1/academic-cycles`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : []))
      .then((rows: AcademicCycle[]) => {
        if (!cancelled) setAcademicCycles(Array.isArray(rows) ? rows : []);
      })
      .catch(() => {
        if (!cancelled) setAcademicCycles([]);
      });
    return () => {
      cancelled = true;
    };
  }, [api]);
  const create = async (event: React.FormEvent) => {
    event.preventDefault();
    if (busy) return;
    setEmailTouched(true);
    const emailError = form.email.trim() ? emailValidationMessage(form.email) : undefined;
    if (emailError) {
      setFieldError(emailError);
      return;
    }
    const passwordError = passwordPolicyError(form.password);
    if (passwordError) {
      setFieldError(passwordError);
      return;
    }
    if (form.roles.includes("STUDENT") && !form.registration_number.trim()) {
      setFieldError("Registration number is required for STUDENT accounts.");
      return;
    }
    if (form.roles.includes("COORDINATOR") && !form.coordinator_academic_cycle_ids.length) {
      setFieldError("Select at least one open academic cycle for this coordinator.");
      return;
    }
    setBusy("create");
    setFieldError("");
    try {
      const response = await fetch(`${api}/api/v1/admin/users`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: form.full_name,
          email: normalizeEmail(form.email),
          password: form.password,
          role: form.roles[0],
          roles: form.roles,
          ...(form.roles.includes("STUDENT")
            ? { registration_number: form.registration_number.trim() }
            : {}),
          ...(form.roles.includes("COORDINATOR")
            ? { coordinator_academic_cycle_ids: form.coordinator_academic_cycle_ids.map(Number) }
            : {}),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFieldError(detail(body));
        return;
      }
      setForm({
        full_name: "",
        email: "",
        password: "",
        roles: ["SUPERVISOR"],
        registration_number: "",
        coordinator_academic_cycle_ids: [],
      });
      setEmailTouched(false);
      setShowCreate(false);
      setNotice("Account created.");
      setPage(1);
      await load();
    } catch {
      setFieldError("The account service is unavailable.");
    } finally {
      setBusy(null);
    }
  };
  const mutate = async () => {
    if (!confirm || busy) return;
    setBusy(confirm.user.id);
    setNotice("");
    try {
      const endpoint = confirm.type === "delete"
        ? `${api}/api/v1/admin/users/${confirm.user.id}`
        : `${api}/api/v1/admin/users/${confirm.user.id}/${confirm.type}`;
      const response = await fetch(
        endpoint,
        confirm.type === "status"
          ? { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: confirm.value === "true" }) }
          : { method: "DELETE", credentials: "include" },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setNotice(detail(body));
        return;
      }
      setConfirm(null);
      setNotice(confirm.type === "delete" ? "Account deleted. Portal access was removed and previous records were preserved." : confirm.value === "true" ? "Account restored by administrator. No verification email is required." : "Account deactivated.");
      await load();
    } catch {
      setNotice("The account service is unavailable.");
    } finally {
      setBusy(null);
    }
  };
  const changePassword = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!passwordUser || busy) return;
    const passwordError = passwordPolicyError(passwordForm.new_password);
    if (passwordError) {
      setPasswordError(passwordError);
      return;
    }
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      setPasswordError("Passwords do not match.");
      return;
    }
    setBusy(passwordUser.id);
    setPasswordError("");
    try {
      const response = await fetch(`${api}/api/v1/admin/users/${passwordUser.id}/password`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(passwordForm),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setPasswordError(detail(body));
        return;
      }
      setPasswordUser(null);
      setPasswordForm({ new_password: "", confirm_password: "" });
      setNotice(`Password changed for ${passwordUser.full_name}. Existing sessions were signed out.`);
    } catch {
      setPasswordError("The account service is unavailable.");
    } finally {
      setBusy(null);
    }
  };
  const editAccount = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editUser || busy) return;
    const emailError = editForm.email.trim() ? emailValidationMessage(editForm.email) : "Email is required.";
    if (emailError) {
      setEditError(emailError);
      return;
    }
    if (!editForm.full_name.trim()) {
      setEditError("Full name is required.");
      return;
    }
    if (editForm.roles.includes("STUDENT") && !editForm.registration_number.trim()) {
      setEditError("Registration number is required for STUDENT accounts.");
      return;
    }
    if (editForm.roles.includes("COORDINATOR") && !editForm.coordinator_academic_cycle_ids.length) {
      setEditError("Select at least one open academic cycle for this coordinator.");
      return;
    }
    setBusy(editUser.id);
    setEditError("");
    try {
      const response = await fetch(`${api}/api/v1/admin/users/${editUser.id}`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: editForm.full_name,
          email: normalizeEmail(editForm.email),
          registration_number: editForm.registration_number.trim() || null,
          role: editForm.roles[0],
          roles: editForm.roles,
          ...(editForm.roles.includes("COORDINATOR")
            ? { coordinator_academic_cycle_ids: editForm.coordinator_academic_cycle_ids.map(Number) }
            : {}),
        }),
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setEditError(detail(body));
        return;
      }
      setEditUser(null);
      setNotice(`Account updated for ${editForm.full_name}. The user must sign in again if account details changed.`);
      await load();
    } catch {
      setEditError("The account service is unavailable.");
    } finally {
      setBusy(null);
    }
  };
  const searchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(1);
    void load();
  };
  return (
    <section aria-labelledby="users-heading">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 id="users-heading" className="text-2xl font-bold tracking-tight">
            Users &amp; Roles
          </h1>
          <p className="mt-1 text-sm text-[#60716b]">
            View assigned roles and manage account status.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3"><p className="text-sm text-[#60716b]">
          {data.total} account{data.total === 1 ? "" : "s"}
        </p><AdminAddButton open={showCreate} label="account" onClick={() => setShowCreate((value) => !value)} /></div>
      </div>
      {notice && (
        <p
          role="status"
          className="mb-4 rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176b66]"
        >
          {notice}
        </p>
      )}
      <div className={`grid gap-5 ${showCreate ? "xl:grid-cols-[minmax(0,1fr)_300px]" : ""}`}>
        <div className="min-w-0">
          <form
            onSubmit={searchSubmit}
            className="mb-4 grid gap-3 rounded-xl border border-[#dce4de] bg-white p-4 sm:grid-cols-[minmax(0,1fr)_140px_120px_auto]"
          >
            <input
              aria-label="Search accounts"
              className={input}
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search name, email, or registration"
            />
            <select
              aria-label="Filter by role"
              className={input}
              value={role}
              onChange={(event) => {
                setRole(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All roles</option>
              {roles.map((item) => (
                <option key={item} value={item}>{roleLabel[item]}</option>
              ))}
            </select>
            <select
              aria-label="Filter by status"
              className={input}
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All statuses</option>
              <option value="true">Active</option>
              <option value="false">Inactive / deleted</option>
            </select>
            <button className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white transition duration-200 hover:bg-[#125650] active:scale-[.98]">
              Search
            </button>
          </form>
          {state === "loading" && (
            <div className="rounded-xl border border-[#dce4de] bg-white p-5 text-sm text-[#60716b]">
              Loading accounts…
            </div>
          )}
          {state === "error" && (
            <div
              role="alert"
              className="rounded-xl border border-[#e6c8c3] bg-[#fff3f0] p-5 text-sm text-[#a43a33]"
            >
              Accounts could not be loaded. Try again.
            </div>
          )}
          {state === "ready" && !data.items.length && (
            <div className="rounded-xl border border-dashed border-[#cbd6d0] bg-white p-5 text-sm text-[#60716b]">
              No accounts match these filters.
            </div>
          )}
          {state === "ready" && Boolean(data.items.length) && (
            <div className="users-table overflow-x-auto rounded-xl border border-[#dce4de] bg-white">
              <table className="w-full table-fixed text-left text-sm">
                <colgroup>
                  <col className="w-[42%]" />
                  <col className="w-[22%]" />
                  <col className="w-[16%]" />
                  <col className="w-[20%]" />
                </colgroup>
                <thead className="bg-[#fbfcfa] text-xs uppercase tracking-wide text-[#60716b]">
                  <tr>
                    <th className="px-4 py-3">Account</th>
                    <th className="px-3 py-3">Role</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#e8ede9]">
                  {data.items.map((user) => (
                    <tr key={user.id}>
                      <td className="px-4 py-3">
                        <p
                          className="truncate font-semibold"
                          title={accountLabel(user)}
                        >
                          {accountLabel(user)}
                        </p>
                        <p
                          className="truncate text-xs text-[#60716b]"
                          title={
                            user.role !== "STUDENT" && user.registration_number
                              ? `${user.email} · ${user.registration_number}`
                              : user.email
                          }
                        >
                          {user.email}
                          {user.role !== "STUDENT" && user.registration_number
                            ? ` · ${user.registration_number}`
                            : ""}
                        </p>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-col items-start gap-1">
                          {selectedRoles(user).map((assignedRole) => <span className={roleBadgeClass} key={`${user.id}-${assignedRole}`}>{roleLabel[assignedRole]}</span>)}
                          {coordinatorCycleNames(user).map((cycleName, index) => (
                            <span className={roleBadgeClass} key={`${user.id}-coordinator-${index}`}>
                              Coordinator · {cycleName}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={
                            user.is_active
                              ? "rounded-full bg-[#e4eee7] px-2 py-1 text-xs font-bold text-[#176b66]"
                              : "rounded-full bg-[#edf0ee] px-2 py-1 text-xs font-bold text-[#58665f]"
                          }
                        >
                          {user.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-wrap gap-1.5" aria-label={`Actions for ${accountLabel(user)}`}>
                          <IconButton label={user.is_active ? "Deactivate account" : "Activate account"} size="sm" variant="secondary" disabled={busy === user.id} onClick={() => setConfirm({ user, type: "status", value: String(!user.is_active) })}><Power size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                          <IconButton label={user.is_active ? "Remove portal access" : "Restore account"} size="sm" variant={user.is_active ? "danger" : "secondary"} disabled={busy === user.id} onClick={() => user.is_active ? setConfirm({ user, type: "delete", value: "delete" }) : setConfirm({ user, type: "status", value: "true" })}>{user.is_active ? <ShieldOff size={15} strokeWidth={1.8} aria-hidden /> : <ShieldCheck size={15} strokeWidth={1.8} aria-hidden />}</IconButton>
                          <IconButton label="Change password" size="sm" variant="secondary" disabled={busy === user.id} onClick={() => { setPasswordUser(user); setPasswordForm({ new_password: "", confirm_password: "" }); setPasswordError(""); }}><KeyRound size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                          <IconButton label="Edit account" size="sm" variant="secondary" disabled={busy === user.id} onClick={() => { setEditUser(user); setEditForm({ full_name: user.full_name, email: user.email, registration_number: user.registration_number ?? "", roles: selectedRoles(user), coordinator_academic_cycle_ids: coordinatorCycleIds(user).map(String) }); setEditError(""); }}><Pencil size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                          <IconButton label="Delete account" size="sm" variant="danger" disabled={busy === user.id} onClick={() => setConfirm({ user, type: "delete", value: "delete" })}><Trash2 size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between text-sm">
            <button
              type="button"
              disabled={page <= 1 || state === "loading"}
              onClick={() => setPage((value) => value - 1)}
              className="rounded-lg border border-[#cbd6d0] px-3 py-2 disabled:opacity-50"
            >
              Previous
            </button>
            <span>Page {data.page}</span>
            <button
              type="button"
              disabled={
                page * data.page_size >= data.total || state === "loading"
              }
              onClick={() => setPage((value) => value + 1)}
              className="rounded-lg border border-[#cbd6d0] px-3 py-2 disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </div>
        {showCreate && <form
          onSubmit={create}
          className="h-fit rounded-xl border border-[#dce4de] bg-white p-5 shadow-[0_2px_12px_rgba(36,55,70,0.035)]"
        >
          <h2 className="font-bold">Create account</h2>
          <div className="mt-4 grid gap-3">
            <label className="grid gap-1 text-sm font-semibold">
              Full name
              <input
                required
                className={input}
                value={form.full_name}
                onChange={(event) =>
                  setForm({ ...form, full_name: event.target.value })
                }
              />
            </label>
            <label className="grid gap-1 text-sm font-semibold">
              Email
              <input
                required
                className={input}
                type="email"
                aria-invalid={Boolean(emailError)}
                value={form.email}
                onChange={(event) => {
                  setForm({ ...form, email: event.target.value });
                  setFieldError("");
                }}
                onBlur={() => setEmailTouched(true)}
              />
              {emailError && (
                <span className="text-sm font-normal text-[#a43a33]">
                  {emailError}
                </span>
              )}
            </label>
            <PasswordField
              label="Password"
              value={form.password}
              error={fieldError.startsWith("Use at least") || fieldError.includes("no more than") ? fieldError : undefined}
              onChange={(password) => { setForm({ ...form, password }); setFieldError(""); }}
            />
            <div className="grid min-w-0 gap-1 text-sm font-semibold">
              <span>Roles</span>
              <RolePicker
                selected={form.roles}
                allowed={roles.filter((item) => item !== "STUDENT")}
                onChange={(nextRoles) => {
                  setFieldError("");
                  setForm({
                    ...form,
                    roles: nextRoles,
                    coordinator_academic_cycle_ids: nextRoles.includes("COORDINATOR") ? form.coordinator_academic_cycle_ids : [],
                    ...(nextRoles.includes("STUDENT") ? {} : { registration_number: "" }),
                  });
                }}
              />
            </div>
            {form.roles.includes("COORDINATOR") && (
              <div className="grid gap-1 text-sm font-semibold">
                <span>Coordinator cycles <span className="text-[#a43a33]">(required)</span></span>
                <CoordinatorCyclePicker
                  cycles={availableCoordinatorCycles}
                  selectedIds={form.coordinator_academic_cycle_ids}
                  onChange={(ids) => {
                    setForm({ ...form, coordinator_academic_cycle_ids: ids });
                    setFieldError("");
                  }}
                />
                <span className="text-xs font-normal text-[#60716b]">Select any number of cycles. Each academic cycle can still have only one coordinator.</span>
                {!availableCoordinatorCycles.length && <span className="text-xs font-normal text-[#a43a33]">No unassigned cycle currently has registration open.</span>}
              </div>
            )}
            {form.roles.includes("STUDENT") && (
              <label className="grid gap-1 text-sm font-semibold">
                Registration number <span className="text-[#a43a33]">(required)</span>
                <input
                  required
                  className={input}
                  value={form.registration_number}
                  onChange={(event) =>
                    setForm({ ...form, registration_number: event.target.value })
                  }
                />
              </label>
            )}
            {fieldError && (
              <p role="alert" className="text-sm text-[#a43a33]">
                {fieldError}
              </p>
            )}
            <button
              disabled={busy !== null || Boolean(emailError)}
              className="rounded-lg bg-[#176b66] px-4 py-2.5 text-sm font-semibold text-white transition duration-200 hover:bg-[#125650] disabled:opacity-60"
            >
              {busy === "create" ? "Creating…" : "Create account"}
            </button>
          </div>
        </form>}
      </div>
      {confirm && (
        <ModalPortal>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-heading"
            className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
          >
            <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="confirm-heading" className="text-lg font-bold">
              {confirm.type === "delete" ? "Confirm account deletion" : confirm.value === "true" ? "Restore account" : "Confirm account change"}
            </h2>
            <p className="mt-2 text-sm text-[#60716b]">
              {confirm.type === "delete" ? `Delete ${accountLabel(confirm.user)}? They will be signed out and unable to sign in. Previous academic records and audit history will be preserved, and the account can be restored later.` : confirm.value === "true" ? `Restore ${accountLabel(confirm.user)}? They will be able to sign in again.` : `Deactivate ${accountLabel(confirm.user)}?`}
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => setConfirm(null)}
                className="rounded-lg border border-[#cbd6d0] px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void mutate()}
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 ${confirm.type === "delete" ? "bg-[#a43a33]" : "bg-[#176b66]"}`}
              >
                {busy ? "Saving…" : confirm.type === "delete" ? "Delete account" : confirm.value === "true" ? "Restore account" : "Confirm"}
              </button>
            </div>
            </div>
          </div>
        </ModalPortal>
      )}
      {passwordUser && (
        <ModalPortal>
          <div role="dialog" aria-modal="true" aria-labelledby="password-heading" className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4">
            <form onSubmit={(event) => void changePassword(event)} className="w-full max-w-xl rounded-xl bg-white p-5 shadow-xl">
            <h2 id="password-heading" className="text-lg font-bold">Change account password</h2>
            <p className="mt-2 text-sm text-[#60716b]">Set a new sign-in password for {passwordUser.full_name}. Existing passwords are never displayed because only one-way password hashes are stored.</p>
            <div className="mt-4 grid gap-3">
              <PasswordField label="New password" value={passwordForm.new_password} guidance disabled={busy === passwordUser.id} error={passwordError && !passwordError.includes("match") ? passwordError : undefined} onChange={(value) => { setPasswordForm({ ...passwordForm, new_password: value }); setPasswordError(""); }} />
              <PasswordField label="Confirm new password" value={passwordForm.confirm_password} confirm disabled={busy === passwordUser.id} error={passwordError.includes("match") ? passwordError : undefined} onChange={(value) => { setPasswordForm({ ...passwordForm, confirm_password: value }); setPasswordError(""); }} />
              {passwordError && <p role="alert" className="text-sm text-[#a43a33]">{passwordError}</p>}
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button type="button" disabled={busy === passwordUser.id} onClick={() => setPasswordUser(null)} className="rounded-lg border border-[#cbd6d0] px-4 py-2 text-sm font-semibold">Cancel</button>
              <button type="submit" disabled={busy === passwordUser.id} className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{busy === passwordUser.id ? "Saving…" : "Change password"}</button>
            </div>
            </form>
          </div>
        </ModalPortal>
      )}
      {editUser && (
        <ModalPortal>
          <div role="dialog" aria-modal="true" aria-labelledby="edit-account-heading" className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4">
            <form onSubmit={(event) => void editAccount(event)} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="edit-account-heading" className="text-lg font-bold">Edit account</h2>
            <p className="mt-2 text-sm text-[#60716b]">Update this account’s profile and role. Password changes are handled separately.</p>
            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-sm font-semibold">Full name<input required className={input} value={editForm.full_name} onChange={(event) => setEditForm({ ...editForm, full_name: event.target.value })} /></label>
              <label className="grid gap-1 text-sm font-semibold">Email<input required type="email" className={input} value={editForm.email} onChange={(event) => setEditForm({ ...editForm, email: event.target.value })} /></label>
              <label className="grid gap-1 text-sm font-semibold">Registration number<input className={input} value={editForm.registration_number} onChange={(event) => setEditForm({ ...editForm, registration_number: event.target.value })} placeholder={editForm.roles.includes("STUDENT") ? "Required for group account" : "Optional"} /></label>
              <div className="grid gap-1 text-sm font-semibold">
                <span>Roles</span>
                <RolePicker
                  selected={editForm.roles}
                  allowed={editForm.roles.includes("STUDENT") ? ["STUDENT"] : roles.filter((item) => item !== "STUDENT")}
                  onChange={(nextRoles) => setEditForm({ ...editForm, roles: nextRoles, coordinator_academic_cycle_ids: nextRoles.includes("COORDINATOR") ? editForm.coordinator_academic_cycle_ids : [] })}
                />
              </div>
              {editForm.roles.includes("COORDINATOR") && (
                <div className="grid gap-1 text-sm font-semibold">
                  <span>Coordinator cycles <span className="text-[#a43a33]">(required)</span></span>
                  <select multiple tabIndex={-1} aria-hidden="true" className="hidden" value={editForm.coordinator_academic_cycle_ids} onChange={() => undefined}>
                    {editCoordinatorCycles.map((cycle) => (
                      <option key={cycle.id} value={cycle.id}>{cycle.display_name} ({cycle.code}){!cycle.registration_open ? " — current assignment" : ""}</option>
                    ))}
                  </select>
                  <CoordinatorCyclePicker
                    cycles={editCoordinatorCycles}
                    selectedIds={editForm.coordinator_academic_cycle_ids}
                    onChange={(ids) => { setEditForm({ ...editForm, coordinator_academic_cycle_ids: ids }); setEditError(""); }}
                  />
                  <span className="text-xs font-normal text-[#60716b]">Select any number of cycles. Each academic cycle can still have only one coordinator.</span>
                </div>
              )}
              {editError && <p role="alert" className="text-sm text-[#a43a33]">{editError}</p>}
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button type="button" disabled={busy === editUser.id} onClick={() => setEditUser(null)} className="rounded-lg border border-[#cbd6d0] px-4 py-2 text-sm font-semibold">Cancel</button>
              <button type="submit" disabled={busy === editUser.id} className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{busy === editUser.id ? "Saving…" : "Save changes"}</button>
            </div>
            </form>
          </div>
        </ModalPortal>
      )}
    </section>
  );
}
