import { useCallback, useEffect, useState } from "react";
import { KeyRound, Pencil, Power, ShieldCheck, ShieldOff, Trash2 } from "lucide-react";
import { PasswordField } from "./PasswordField";
import { passwordPolicyError } from "./passwordPolicy";
import { emailValidationMessage, normalizeEmail } from "./emailValidation";
import { AdminAddButton } from "./ui/AdminAddButton";
import { IconButton } from "./ui/IconButton";

type Role = "STUDENT" | "SUPERVISOR" | "COORDINATOR" | "PANEL_MEMBER" | "ADMIN";
type User = {
  id: number;
  full_name: string;
  group_name?: string | null;
  email: string;
  registration_number: string | null;
  role: Role;
  is_active: boolean;
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
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [passwordUser, setPasswordUser] = useState<User | null>(null);
  const [passwordForm, setPasswordForm] = useState({ new_password: "", confirm_password: "" });
  const [passwordError, setPasswordError] = useState("");
  const [editUser, setEditUser] = useState<User | null>(null);
  const [editForm, setEditForm] = useState({ full_name: "", email: "", registration_number: "", role: "SUPERVISOR" as Role });
  const [editError, setEditError] = useState("");
  const [confirm, setConfirm] = useState<{
    user: User;
    type: "status" | "delete" | "permanent";
    value: string;
  } | null>(null);
  const [form, setForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "SUPERVISOR" as Role,
    registration_number: "",
  });
  const [fieldError, setFieldError] = useState("");
  const [showCreate, setShowCreate] = useState(false);
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
    if (form.role === "STUDENT" && !form.registration_number.trim()) {
      setFieldError("Registration number is required for STUDENT accounts.");
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
          role: form.role,
          ...(form.role === "STUDENT"
            ? { registration_number: form.registration_number.trim() }
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
        role: "SUPERVISOR",
        registration_number: "",
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
        : confirm.type === "permanent"
          ? `${api}/api/v1/admin/users/${confirm.user.id}/permanent`
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
      setNotice(confirm.type === "permanent" ? "Account permanently deleted." : confirm.type === "delete" ? "Portal access removed. Previous records are preserved." : confirm.value === "true" ? "Account activated by administrator. No verification email is required." : "Account deactivated.");
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
    if (editForm.role === "STUDENT" && !editForm.registration_number.trim()) {
      setEditError("Registration number is required for STUDENT accounts.");
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
          role: editForm.role,
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
              <option value="false">Inactive</option>
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
                        <span className="inline-flex rounded-full bg-[#eef0ff] px-2 py-1 text-xs font-bold text-[#263fae]">
                          {roleLabel[user.role]}
                        </span>
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
                          <IconButton label={user.is_active ? "Remove portal access" : "Allow portal access"} size="sm" variant={user.is_active ? "danger" : "secondary"} disabled={busy === user.id} onClick={() => user.is_active ? setConfirm({ user, type: "delete", value: "delete" }) : setConfirm({ user, type: "status", value: "true" })}>{user.is_active ? <ShieldOff size={15} strokeWidth={1.8} aria-hidden /> : <ShieldCheck size={15} strokeWidth={1.8} aria-hidden />}</IconButton>
                          <IconButton label="Change password" size="sm" variant="secondary" disabled={busy === user.id} onClick={() => { setPasswordUser(user); setPasswordForm({ new_password: "", confirm_password: "" }); setPasswordError(""); }}><KeyRound size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                          <IconButton label="Edit account" size="sm" variant="secondary" disabled={busy === user.id} onClick={() => { setEditUser(user); setEditForm({ full_name: user.full_name, email: user.email, registration_number: user.registration_number ?? "", role: user.role }); setEditError(""); }}><Pencil size={15} strokeWidth={1.8} aria-hidden /></IconButton>
                          <IconButton label="Delete permanently" size="sm" variant="danger" disabled={busy === user.id} onClick={() => setConfirm({ user, type: "permanent", value: "delete" })}><Trash2 size={15} strokeWidth={1.8} aria-hidden /></IconButton>
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
            <label className="admin-create-role grid min-w-0 gap-1 text-sm font-semibold">
              Role
              <select
                className={`${input} min-w-0 pr-10`}
                value={form.role}
                onChange={(event) => {
                  const nextRole = event.target.value as Role;
                  setFieldError("");
                  setForm({
                    ...form,
                    role: nextRole,
                    ...(nextRole === "STUDENT" ? {} : { registration_number: "" }),
                  });
                }}
              >
                {roles.filter((item) => item !== "STUDENT").map((item) => (
                  <option key={item} value={item}>{roleLabel[item]}</option>
                ))}
              </select>
            </label>
            {form.role === "STUDENT" && (
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
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="confirm-heading"
          className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="confirm-heading" className="text-lg font-bold">
              {confirm.type === "permanent" ? "Confirm permanent deletion" : confirm.type === "delete" ? "Confirm access removal" : confirm.value === "true" ? "Confirm portal access" : "Confirm account change"}
            </h2>
            <p className="mt-2 text-sm text-[#60716b]">
              {confirm.type === "permanent" ? `Permanently delete ${accountLabel(confirm.user)}? This cannot be undone. Accounts with linked academic or audit history must use Remove access instead.` : confirm.type === "delete" ? `Remove portal access for ${accountLabel(confirm.user)}? They will be signed out and unable to sign in. All previous records and audit history will be preserved.` : confirm.value === "true" ? `Allow portal access for ${accountLabel(confirm.user)}? They will be able to sign in again.` : `Deactivate ${accountLabel(confirm.user)}?`}
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
                className={`rounded-lg px-4 py-2 text-sm font-semibold text-white disabled:opacity-60 ${confirm.type === "permanent" ? "bg-[#a43a33]" : "bg-[#176b66]"}`}
              >
                {busy ? "Saving…" : confirm.type === "permanent" ? "Delete permanently" : confirm.type === "delete" ? "Remove access" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
      {passwordUser && (
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
      )}
      {editUser && (
        <div role="dialog" aria-modal="true" aria-labelledby="edit-account-heading" className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4">
          <form onSubmit={(event) => void editAccount(event)} className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="edit-account-heading" className="text-lg font-bold">Edit account</h2>
            <p className="mt-2 text-sm text-[#60716b]">Update this account’s profile and role. Password changes are handled separately.</p>
            <div className="mt-4 grid gap-3">
              <label className="grid gap-1 text-sm font-semibold">Full name<input required className={input} value={editForm.full_name} onChange={(event) => setEditForm({ ...editForm, full_name: event.target.value })} /></label>
              <label className="grid gap-1 text-sm font-semibold">Email<input required type="email" className={input} value={editForm.email} onChange={(event) => setEditForm({ ...editForm, email: event.target.value })} /></label>
              <label className="grid gap-1 text-sm font-semibold">Registration number<input className={input} value={editForm.registration_number} onChange={(event) => setEditForm({ ...editForm, registration_number: event.target.value })} placeholder={editForm.role === "STUDENT" ? "Required for group account" : "Optional"} /></label>
              <label className="grid gap-1 text-sm font-semibold">Role<select className={input} value={editForm.role} onChange={(event) => setEditForm({ ...editForm, role: event.target.value as Role })}>{(editForm.role === "STUDENT" ? ["STUDENT"] : roles.filter((item) => item !== "STUDENT")).map((item) => <option key={item} value={item}>{roleLabel[item as Role]}</option>)}</select></label>
              {editError && <p role="alert" className="text-sm text-[#a43a33]">{editError}</p>}
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button type="button" disabled={busy === editUser.id} onClick={() => setEditUser(null)} className="rounded-lg border border-[#cbd6d0] px-4 py-2 text-sm font-semibold">Cancel</button>
              <button type="submit" disabled={busy === editUser.id} className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">{busy === editUser.id ? "Saving…" : "Save changes"}</button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
