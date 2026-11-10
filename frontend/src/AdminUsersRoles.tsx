import { useCallback, useEffect, useState } from "react";
import { PasswordField } from "./PasswordField";
import { passwordPolicyError } from "./passwordPolicy";
import { emailValidationMessage, normalizeEmail } from "./emailValidation";

type Role = "STUDENT" | "SUPERVISOR" | "COORDINATOR" | "PANEL_MEMBER" | "ADMIN";
type User = {
  id: number;
  full_name: string;
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
  STUDENT: "Student",
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

export function AdminUsersRoles({ api }: { api: string }) {
  const [data, setData] = useState<Page>({
    items: [],
    page: 1,
    page_size: 20,
    total: 0,
  });
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [search, setSearch] = useState("");
  const [role, setRole] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState("");
  const [emailTouched, setEmailTouched] = useState(false);
  const [busy, setBusy] = useState<number | "create" | null>(null);
  const [confirm, setConfirm] = useState<{
    user: User;
    type: "status";
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
      const response = await fetch(
        `${api}/api/v1/admin/users/${confirm.user.id}/${confirm.type}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: confirm.value === "true" }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setNotice(detail(body));
        return;
      }
      setConfirm(null);
      setNotice("Account updated.");
      await load();
    } catch {
      setNotice("The account service is unavailable.");
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
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 id="users-heading" className="text-2xl font-bold tracking-tight">
            Users &amp; Roles
          </h1>
          <p className="mt-1 text-sm text-[#60716b]">
            View assigned roles and manage account status.
          </p>
        </div>
        <p className="text-sm text-[#60716b]">
          {data.total} account{data.total === 1 ? "" : "s"}
        </p>
      </div>
      {notice && (
        <p
          role="status"
          className="mb-4 rounded-lg bg-[#e4eee7] px-3 py-2 text-sm text-[#176b66]"
        >
          {notice}
        </p>
      )}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
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
                          title={user.full_name}
                        >
                          {user.full_name}
                        </p>
                        <p
                          className="truncate text-xs text-[#60716b]"
                          title={
                            user.registration_number
                              ? `${user.email} · ${user.registration_number}`
                              : user.email
                          }
                        >
                          {user.email}
                          {user.registration_number
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
                        <button
                          type="button"
                          disabled={busy === user.id}
                          onClick={() =>
                            setConfirm({
                              user,
                              type: "status",
                              value: String(!user.is_active),
                            })
                          }
                          className="w-full rounded-lg border border-[#b8cdc1] px-2 py-1.5 text-xs font-semibold text-[#176b66] transition duration-200 hover:bg-[#e4eee7] disabled:opacity-60"
                        >
                          {user.is_active ? "Deactivate" : "Activate"}
                        </button>
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
        <form
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
                {roles.map((item) => (
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
        </form>
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
              Confirm account change
            </h2>
            <p className="mt-2 text-sm text-[#60716b]">
              {`${confirm.value === "true" ? "Activate" : "Deactivate"} ${confirm.user.full_name}?`}
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
                className="rounded-lg bg-[#176b66] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
              >
                {busy ? "Saving…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
