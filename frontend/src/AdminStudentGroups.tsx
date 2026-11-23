import { FormEvent, useEffect, useMemo, useState } from "react";
import { BackButton, StatusBadge } from "./ui";

type Cycle = {
  id: number;
  code: string;
  display_name: string;
  academic_year?: number | null;
  session?: string | null;
};
type Member = {
  id: number;
  full_name: string;
  registration_number: string;
  email: string | null;
  designation?: string;
  is_active?: boolean;
};
type Group = {
  id: number;
  group_number?: number | null;
  group_name: string;
  group_name_assigned?: boolean;
  group_email: string;
  academic_cycle_id: number;
  academic_cycle?: string | null;
  status: string;
  approval_status?: string;
  is_active: boolean;
  member_count?: number;
  min_group_size?: number | null;
  max_group_size?: number | null;
  group_policy?: { min_group_size: number; max_group_size: number } | null;
  project?: { title?: string | null } | null;
  supervisor?: { name?: string | null } | null;
  members: Member[];
};
type Version = {
  id: number;
  version_number: number;
  original_filename: string;
  uploaded_at: string;
};
type ReviewEvent = {
  id: number;
  status: string;
  reviewer?: { name?: string | null } | null;
  reviewed_at?: string | null;
  comment?: string | null;
};
type Requirement = {
  id: number;
  requirement_name: string;
  requirement_section?: string | null;
  is_required: boolean;
  current_status: string;
  submitted_file_name?: string | null;
  submitted_at?: string | null;
  versions: Version[];
  review_history: ReviewEvent[];
};
type GroupArchive = {
  id: number;
  group_id: number;
  cycle_id: number;
  group_code: string;
  project_title?: string | null;
  project?: { title?: string | null } | null;
  members: Array<{
    id: number;
    name: string;
    registration_number?: string | null;
    email?: string | null;
    designation?: string | null;
  }>;
  supervisor?: { name?: string | null } | null;
  requirements: Requirement[];
};
type ErrorBody = { detail?: string | { message?: string } };
type LoadState = "idle" | "loading" | "ready" | "error";
type MemberForm = {
  full_name: string;
  registration_number: string;
  email: string;
};
type CollaborationCredential = {
  member_id: number;
  name: string;
  registration_number: string;
  password_set: boolean;
  reset_requested: boolean;
};
type CollaborationCredentialsResponse = {
  group_id: number;
  channel_id: number | null;
  channel_status: string | null;
  members: CollaborationCredential[];
};

const readPositiveId = (name: string) => {
  const value = Number(new URLSearchParams(window.location.search).get(name));
  return Number.isInteger(value) && value > 0 ? value : null;
};
const writeSelection = (
  cycleId: number | null,
  groupId: number | null = null,
) => {
  const url = new URL(window.location.href);
  if (cycleId === null) {
    url.searchParams.delete("cycle_id");
    url.searchParams.delete("group_id");
  } else {
    url.searchParams.set("cycle_id", String(cycleId));
    if (groupId === null) url.searchParams.delete("group_id");
    else url.searchParams.set("group_id", String(groupId));
  }
  window.history.replaceState(
    { adminPage: "studentGroups", cycleId, groupId },
    "",
    `${url.pathname}${url.search}${url.hash}`,
  );
};
const errorText = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as ErrorBody).detail;
  return typeof detail === "string" ? detail : detail?.message || fallback;
};
const display = (value: unknown, fallback = "Not assigned") =>
  value === null || value === undefined || String(value).trim() === ""
    ? fallback
    : String(value);
const activeMemberCount = (group: Group) =>
  group.member_count ??
  group.members.filter((member) => member.is_active !== false).length;
const groupCapacity = (group: Group) =>
  group.max_group_size ?? group.group_policy?.max_group_size ?? null;

export function groupsForCycle(groups: Group[], selectedCycleId: number) {
  return groups.filter((group) => group.academic_cycle_id === selectedCycleId);
}

export function AdminStudentGroups({ api }: { api: string }) {
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [archive, setArchive] = useState<GroupArchive | null>(null);
  const [cycleState, setCycleState] = useState<LoadState>("loading");
  const [groupState, setGroupState] = useState<LoadState>("idle");
  const [detailState, setDetailState] = useState<LoadState>("idle");
  const [notice, setNotice] = useState("");
  const [cycleError, setCycleError] = useState("");
  const [groupError, setGroupError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [reloadToken, setReloadToken] = useState(0);
  const [confirm, setConfirm] = useState<{
    group: Group;
    action: "deactivate" | "reject" | "delete";
  } | null>(null);
  const [busy, setBusy] = useState(false);
  const [approvalTarget, setApprovalTarget] = useState<Group | null>(null);
  const [approvalName, setApprovalName] = useState("");
  const [approvalError, setApprovalError] = useState("");
  const [approvalBusy, setApprovalBusy] = useState(false);
  const [memberTarget, setMemberTarget] = useState<Group | null>(null);
  const [memberForm, setMemberForm] = useState<MemberForm>({
    full_name: "",
    registration_number: "",
    email: "",
  });
  const [memberError, setMemberError] = useState("");
  const [memberBusy, setMemberBusy] = useState(false);
  const [collaborationCredentials, setCollaborationCredentials] = useState<CollaborationCredentialsResponse | null>(null);
  const [collaborationState, setCollaborationState] = useState<LoadState>("idle");
  const [collaborationError, setCollaborationError] = useState("");
  const [collaborationReload, setCollaborationReload] = useState(0);
  const [collaborationBusyMemberId, setCollaborationBusyMemberId] = useState<number | null>(null);

  const selectedCycle = useMemo(
    () => cycles.find((cycle) => cycle.id === selectedCycleId) ?? null,
    [cycles, selectedCycleId],
  );
  const selectedGroup = useMemo(
    () => groups.find((group) => group.id === selectedGroupId) ?? null,
    [groups, selectedGroupId],
  );

  useEffect(() => {
    const controller = new AbortController();
    const loadCycles = async () => {
      setCycleState("loading");
      setCycleError("");
      try {
        const response = await fetch(`${api}/api/v1/academic-cycles`, {
          credentials: "include",
          signal: controller.signal,
        });
        const body = await response.json().catch(() => null);
        if (!response.ok)
          throw new Error(errorText(body, "FYP cycles could not be loaded."));
        const available = Array.isArray(body) ? (body as Cycle[]) : [];
        setCycles(available);
        const requestedCycleId = readPositiveId("cycle_id");
        if (
          requestedCycleId !== null &&
          available.some((cycle) => cycle.id === requestedCycleId)
        )
          setSelectedCycleId(requestedCycleId);
        else {
          setSelectedCycleId(null);
          if (requestedCycleId !== null) writeSelection(null);
        }
        setCycleState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setCycleState("error");
          setCycleError(
            error instanceof Error
              ? error.message
              : "FYP cycles could not be loaded.",
          );
        }
      }
    };
    void loadCycles();
    return () => controller.abort();
  }, [api]);

  useEffect(() => {
    if (selectedCycleId === null) {
      const reset = window.setTimeout(() => {
        setGroups([]);
        setSelectedGroupId(null);
        setArchive(null);
        setGroupState("idle");
        setDetailState("idle");
      }, 0);
      return () => window.clearTimeout(reset);
    }
    const controller = new AbortController();
    const loadGroups = async () => {
      setGroupState("loading");
      setGroupError("");
      setGroups([]);
      setSelectedGroupId(null);
      setArchive(null);
      setDetailState("idle");
      try {
        const response = await fetch(
          `${api}/api/v1/admin/student-groups?${new URLSearchParams({ cycle_id: String(selectedCycleId) })}`,
          { credentials: "include", signal: controller.signal },
        );
        const body = await response.json().catch(() => ({}));
        if (!response.ok)
          throw new Error(
            errorText(body, "Groups for this cycle could not be loaded."),
          );
        const items =
          body &&
          typeof body === "object" &&
          Array.isArray((body as { items?: unknown }).items)
            ? (body as { items: Group[] }).items
            : [];
        setGroups(groupsForCycle(items, selectedCycleId));
        setGroupState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setGroupState("error");
          setGroupError(
            error instanceof Error
              ? error.message
              : "Groups for this cycle could not be loaded.",
          );
        }
      }
    };
    void loadGroups();
    return () => controller.abort();
  }, [api, reloadToken, selectedCycleId]);

  useEffect(() => {
    if (selectedCycleId === null || groupState !== "ready") return;
    const requestedGroupId = readPositiveId("group_id");
    if (
      requestedGroupId !== null &&
      groups.some((group) => group.id === requestedGroupId)
    ) {
      const select = window.setTimeout(
        () => setSelectedGroupId(requestedGroupId),
        0,
      );
      return () => window.clearTimeout(select);
    }
    if (requestedGroupId !== null) writeSelection(selectedCycleId);
  }, [groupState, groups, selectedCycleId]);

  useEffect(() => {
    if (selectedCycleId === null || selectedGroupId === null) return;
    const controller = new AbortController();
    const loadDetail = async () => {
      setDetailState("loading");
      setDetailError("");
      try {
        const response = await fetch(
          `${api}/api/v1/admin/document-archive/cycles/${selectedCycleId}/groups/${selectedGroupId}`,
          { credentials: "include", signal: controller.signal },
        );
        const body = await response.json().catch(() => ({}));
        if (!response.ok)
          throw new Error(
            errorText(body, "The selected group details could not be loaded."),
          );
        const result = body as {
          cycle?: { id?: number };
          group?: GroupArchive;
        };
        if (
          result.cycle?.id !== selectedCycleId ||
          result.group?.cycle_id !== selectedCycleId ||
          result.group.group_id !== selectedGroupId
        )
          throw new Error(
            "The selected group does not belong to the selected cycle.",
          );
        setArchive(result.group);
        setDetailState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setArchive(null);
          setDetailState("error");
          setDetailError(
            error instanceof Error
              ? error.message
              : "The selected group details could not be loaded.",
          );
        }
      }
    };
    void loadDetail();
    return () => controller.abort();
  }, [api, selectedCycleId, selectedGroupId]);

  useEffect(() => {
    if (selectedCycleId === null || selectedGroupId === null) return;
    const controller = new AbortController();
    const loadCredentials = async () => {
      setCollaborationState("loading");
      setCollaborationError("");
      try {
        const response = await fetch(
          `${api}/api/v1/admin/student-groups/${selectedGroupId}/collaboration-credentials?${new URLSearchParams({ cycle_id: String(selectedCycleId) })}`,
          { credentials: "include", signal: controller.signal },
        );
        const body = await response.json().catch(() => ({}));
        if (!response.ok)
          throw new Error(errorText(body, "Collaboration credential status could not be loaded."));
        setCollaborationCredentials(body as CollaborationCredentialsResponse);
        setCollaborationState("ready");
      } catch (error) {
        if (!controller.signal.aborted) {
          setCollaborationState("error");
          setCollaborationError(error instanceof Error ? error.message : "Collaboration credential status could not be loaded.");
        }
      }
    };
    void loadCredentials();
    return () => controller.abort();
  }, [api, collaborationReload, selectedCycleId, selectedGroupId]);

  useEffect(() => {
    if (detailState !== "ready" || collaborationState !== "ready") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("focus") !== "collaboration-reset") return;
    const memberId = readPositiveId("member_id");
    const target = memberId
      ? document.getElementById(`collaboration-reset-member-${memberId}`)
      : document.getElementById("collaboration-credentials-heading");
    if (!target) return;
    const timer = window.setTimeout(() => target.scrollIntoView({ behavior: "smooth", block: "start" }), 0);
    return () => window.clearTimeout(timer);
  }, [collaborationState, detailState]);

  const selectCycle = (cycleId: number | null) => {
    setNotice("");
    setCycleError("");
    setGroupError("");
    setDetailError("");
    setCollaborationCredentials(null);
    setCollaborationState("idle");
    setCollaborationError("");
    setSelectedCycleId(cycleId);
    setSelectedGroupId(null);
    setArchive(null);
    writeSelection(cycleId);
  };
  const openGroup = (groupId: number) => {
    if (
      selectedCycleId === null ||
      !groups.some((group) => group.id === groupId)
    )
      return;
    setNotice("");
    setDetailError("");
    setCollaborationCredentials(null);
    setCollaborationState("idle");
    setCollaborationError("");
    setSelectedGroupId(groupId);
    writeSelection(selectedCycleId, groupId);
  };
  const openApproval = (group: Group) => {
    setApprovalTarget(group);
    setApprovalName(group.group_name_assigned ? group.group_name : "");
    setApprovalError("");
  };
  const openAddMember = (group: Group) => {
    setMemberTarget(group);
    setMemberError("");
    setMemberForm({ full_name: "", registration_number: "", email: "" });
  };

  const addMember = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!memberTarget || memberBusy) return;
    setMemberBusy(true);
    setMemberError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${memberTarget.id}/members`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(memberForm),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(
          errorText(body, "The student could not be added to this group."),
        );
      const member = body.member as Member;
      setGroups((current) =>
        current.map((group) =>
          group.id === memberTarget.id
            ? {
                ...group,
                members: [...group.members, member],
                member_count: body.member_count,
              }
            : group,
        ),
      );
      setArchive((current) =>
        current && current.group_id === memberTarget.id
          ? {
              ...current,
              members: [
                ...current.members,
                {
                  id: member.id,
                  name: member.full_name,
                  registration_number: member.registration_number,
                  email: member.email,
                  designation: "MEMBER",
                },
              ],
            }
          : current,
      );
      setMemberTarget(null);
      setNotice(
        `${member.full_name} was added to the group. Portal access remains under the group account.`,
      );
    } catch (error) {
      setMemberError(
        error instanceof Error
          ? error.message
          : "The student could not be added to this group.",
      );
    } finally {
      setMemberBusy(false);
    }
  };

  const resetCollaborationCredential = async (member: CollaborationCredential) => {
    if (selectedCycleId === null || selectedGroupId === null || collaborationBusyMemberId !== null) return;
    if (!window.confirm(`Remove the old collaboration password for ${member.name}? They will create a new password from the Student portal.`)) return;
    setCollaborationBusyMemberId(member.member_id);
    setCollaborationError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${selectedGroupId}/collaboration-credentials/${member.member_id}/reset?${new URLSearchParams({ cycle_id: String(selectedCycleId) })}`,
        { method: "POST", credentials: "include" },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(errorText(body, "The collaboration password could not be reset."));
      setNotice(`The old collaboration password for ${body.member_name || member.name} was removed. They can now create a new password in the Student portal.`);
      setCollaborationReload((value) => value + 1);
    } catch (error) {
      setCollaborationError(error instanceof Error ? error.message : "The collaboration password could not be reset.");
    } finally {
      setCollaborationBusyMemberId(null);
    }
  };

  const approveGroup = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!approvalTarget || approvalBusy) return;
    const name = approvalName.trim();
    if (!name) {
      setApprovalError("Assign an official group name before approving.");
      return;
    }
    setApprovalBusy(true);
    setApprovalError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${approvalTarget.id}/activate`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ group_name: name }),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(errorText(body, "The group could not be approved."));
      setApprovalTarget(null);
      setApprovalName("");
      setNotice(
        `${name} was approved and can now log in with its group credentials.`,
      );
      setReloadToken((value) => value + 1);
    } catch (error) {
      setApprovalError(
        error instanceof Error
          ? error.message
          : "The group could not be approved.",
      );
    } finally {
      setApprovalBusy(false);
    }
  };

  const mutate = async () => {
    if (!confirm || busy) return;
    const { group, action } = confirm;
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${group.id}${action === "delete" ? "" : `/${action}`}`,
        {
          method: action === "delete" ? "DELETE" : "PATCH",
          credentials: "include",
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok) {
        setNotice(errorText(body, "The group change could not be completed."));
        return;
      }
      if (action === "delete" && selectedGroupId === group.id) {
        setSelectedGroupId(null);
        setArchive(null);
        if (selectedCycleId !== null) writeSelection(selectedCycleId);
      }
      setConfirm(null);
      setNotice(
        action === "delete" ? "Student group deleted." : "Student group status updated.",
      );
      setReloadToken((value) => value + 1);
    } catch {
      setNotice("The student group service is unavailable.");
    } finally {
      setBusy(false);
    }
  };

  const memberFormField = (
    name: keyof MemberForm,
    label: string,
    type = "text",
    placeholder = "",
  ) => (
    <label className="grid gap-1 text-sm font-semibold text-fy-text">
      {label}
      <input
        required
        type={type}
        value={memberForm[name]}
        onChange={(event) =>
          setMemberForm((current) => ({
            ...current,
            [name]: event.target.value,
          }))
        }
        placeholder={placeholder}
        className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2.5 font-normal outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
      />
    </label>
  );

  return (
    <section aria-labelledby="student-groups-heading">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-fy-text-secondary">
            {selectedCycle ? "Selected cycle" : "FYP Groups"}
          </p>
          <h1
            id="student-groups-heading"
            className="text-2xl font-bold tracking-tight"
          >
            {selectedCycle ? selectedCycle.display_name : "FYP Cycles"}
          </h1>
          <p className="mt-1 text-sm text-fy-text-secondary">
            {selectedCycle ? (
              <>
                Viewing groups and document history for{" "}
                <strong className="text-fy-text">{selectedCycle.code}</strong>
                {selectedCycle.academic_year
                  ? ` · ${selectedCycle.academic_year}`
                  : ""}
                {selectedCycle.session ? ` · ${selectedCycle.session}` : ""}.
              </>
            ) : (
              "Select an academic cycle before opening its groups and document history."
            )}
          </p>
        </div>
        {selectedCycle && (
          <label className="grid gap-1 text-sm font-semibold text-fy-text">
            Switch cycle
            <select
              value={selectedCycleId ?? ""}
              onChange={(event) =>
                selectCycle(
                  event.target.value ? Number(event.target.value) : null,
                )
              }
              className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2"
            >
              <option value="">Choose a cycle</option>
              {cycles.map((cycle) => (
                <option key={cycle.id} value={cycle.id}>
                  {cycle.display_name} ({cycle.code})
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      {notice && (
        <p
          role="status"
          className="mb-4 rounded-lg bg-fy-success-soft px-3 py-2 text-sm text-fy-success"
        >
          {notice}
        </p>
      )}
      {cycleState === "loading" && (
        <div className="rounded-xl border border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">
          Loading FYP cycles...
        </div>
      )}
      {cycleState === "error" && (
        <div
          role="alert"
          className="rounded-xl border border-fy-danger bg-fy-danger-soft p-5 text-sm text-fy-danger"
        >
          {cycleError || "FYP cycles could not be loaded."}
        </div>
      )}
      {cycleState === "ready" && selectedCycleId === null && !cycles.length && (
        <div className="rounded-xl border border-dashed border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">
          No FYP cycles are configured.
        </div>
      )}
      {cycleState === "ready" &&
        selectedCycleId === null &&
        cycles.length > 0 && (
          <div aria-label="FYP cycles" className="grid gap-3 sm:grid-cols-2">
            {cycles.map((cycle) => (
              <button
                type="button"
                key={cycle.id}
                onClick={() => selectCycle(cycle.id)}
                className="rounded-xl border border-fy-border bg-fy-surface p-5 text-left shadow-sm transition hover:border-fy-brand hover:shadow-md"
              >
                <span className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                  Academic cycle
                </span>
                <strong className="mt-1 block text-lg text-fy-text">
                  {cycle.display_name}
                </strong>
                <span className="mt-1 block text-sm text-fy-text-secondary">
                  {cycle.code}
                  {cycle.academic_year ? ` · ${cycle.academic_year}` : ""}
                  {cycle.session ? ` · ${cycle.session}` : ""}
                </span>
                <span className="mt-4 block text-sm font-semibold text-fy-brand">
                  View relevant groups
                </span>
              </button>
            ))}
          </div>
        )}
      {selectedCycle && (
        <section aria-labelledby="selected-cycle-heading">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-fy-border bg-fy-brand-soft p-4">
            <div>
              <BackButton onClick={() => selectCycle(null)}>
                Back to FYP cycles
              </BackButton>
              <p className="mt-2 text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                Selected cycle
              </p>
              <h2
                id="selected-cycle-heading"
                className="text-xl font-bold text-fy-text"
              >
                {selectedCycle.display_name}
              </h2>
              <p className="text-sm text-fy-text-secondary">
                {selectedCycle.code}
              </p>
            </div>
            <p className="text-sm font-semibold text-fy-text-secondary">
              {groupState === "ready"
                ? `${groups.length} group${groups.length === 1 ? "" : "s"}`
                : ""}
            </p>
          </div>
          {groupState === "loading" && (
            <div className="rounded-xl border border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">
              Loading groups for {selectedCycle.display_name}...
            </div>
          )}
          {groupState === "error" && (
            <div
              role="alert"
              className="rounded-xl border border-fy-danger bg-fy-danger-soft p-5 text-sm text-fy-danger"
            >
              {groupError || "Groups for this cycle could not be loaded."}
            </div>
          )}
          {groupState === "ready" && !groups.length && (
            <div className="rounded-xl border border-dashed border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">
              No FYP groups belong to {selectedCycle.display_name}.
            </div>
          )}
          {groupState === "ready" && groups.length > 0 && (
            <div className="grid gap-4">
              {groups.map((group) => {
                const count = activeMemberCount(group);
                const capacity = groupCapacity(group);
                const canAddMember =
                  group.is_active && capacity !== null && count < capacity;
                return (
                  <article
                    key={group.id}
                    className={`rounded-xl border bg-fy-surface p-5 ${selectedGroupId === group.id ? "border-fy-brand shadow-md" : "border-fy-border"}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-4">
                      <button
                        type="button"
                        onClick={() => openGroup(group.id)}
                        className="text-left"
                      >
                        <span className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                          Group {group.group_number ?? "—"} ·{" "}
                          {selectedCycle.display_name}
                        </span>
                        <h3 className="mt-1 text-lg font-bold text-fy-text">
                          {group.group_name}
                        </h3>
                        <p className="text-sm text-fy-text-secondary">
                          {group.group_email}
                        </p>
                        <span className="mt-2 block text-sm font-semibold text-fy-brand">
                          {selectedGroupId === group.id
                            ? "Selected group"
                            : "Open group details"}
                        </span>
                      </button>
                      <div className="text-right">
                        <StatusBadge
                          status={
                            group.is_active
                              ? "ACTIVE"
                              : group.approval_status || "PENDING"
                          }
                        />
                        {!group.is_active && (
                          <p className="mt-1 text-xs text-fy-text-secondary">
                            {group.approval_status === "REJECTED"
                              ? "Signup rejected"
                              : group.group_name_assigned
                                ? "Awaiting activation"
                                : "Awaiting admin approval"}
                          </p>
                        )}
                        <p className="mt-2 text-xs font-semibold text-fy-text-secondary">
                          Members {count}
                          {capacity !== null ? ` / ${capacity}` : ""}
                        </p>
                      </div>
                    </div>
                    <div className="mt-4 overflow-x-auto">
                      <table className="w-full min-w-[900px] text-left text-sm">
                        <thead className="border-b border-fy-border text-xs uppercase tracking-wide text-fy-text-secondary">
                          <tr>
                            <th className="px-2 py-2">Member</th>
                            <th className="px-2 py-2">Registration</th>
                            <th className="px-2 py-2">Email</th>
                            <th className="px-2 py-2">Role</th>
                            <th className="px-2 py-2">Project Title</th>
                            <th className="px-2 py-2">Supervisor</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-fy-border">
                          {group.members.length ? (
                            group.members.map((member) => (
                              <tr key={member.id}>
                                <td className="px-2 py-2 font-semibold">
                                  {member.full_name}
                                </td>
                                <td className="px-2 py-2">
                                  {member.registration_number}
                                </td>
                                <td className="px-2 py-2">
                                  {member.email || "Not assigned"}
                                </td>
                                <td className="px-2 py-2">
                                  {member.designation === "LEADER"
                                    ? "Leader"
                                    : "Member"}
                                </td>
                                <td className="px-2 py-2">
                                  {group.project?.title?.trim() ||
                                    "Not assigned"}
                                </td>
                                <td className="px-2 py-2">
                                  {group.supervisor?.name?.trim() ||
                                    "Not assigned"}
                                </td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td
                                colSpan={6}
                                className="px-2 py-3 text-fy-text-secondary"
                              >
                                No active members assigned.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-xs text-fy-text-secondary">
                        {capacity !== null && count < capacity
                          ? `${capacity - count} member slot${capacity - count === 1 ? "" : "s"} available`
                          : capacity !== null
                            ? "Group is at capacity"
                            : "No group limit configured"}
                      </p>
                      <div className="flex flex-wrap justify-end gap-2">
                        {canAddMember && (
                          <button
                            type="button"
                            onClick={() => openAddMember(group)}
                            className="rounded-lg bg-fy-brand px-3 py-2 text-sm font-semibold text-white shadow-sm transition hover:brightness-95"
                          >
                            Add member
                          </button>
                        )}
                        {group.is_active ? (
                          <>
                            <button
                              type="button"
                              onClick={() => openApproval(group)}
                              className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-brand"
                            >
                              {group.group_name_assigned
                                ? "Edit group name"
                                : "Assign group name"}
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                setConfirm({ group, action: "deactivate" })
                              }
                              className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-success"
                            >
                              Deactivate
                            </button>
                          </>
                        ) : (
                          <button
                            type="button"
                            onClick={() => openApproval(group)}
                            className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-success"
                          >
                            {group.group_name_assigned
                              ? "Approve / activate"
                              : "Approve signup"}
                          </button>
                        )}
                        {!group.is_active &&
                          group.approval_status === "PENDING" && (
                            <button
                              type="button"
                              onClick={() =>
                                setConfirm({ group, action: "reject" })
                              }
                              className="rounded-lg border border-fy-danger px-3 py-2 text-sm font-semibold text-fy-danger"
                            >
                              Reject signup
                            </button>
                          )}
                        <button
                          type="button"
                          onClick={() =>
                            setConfirm({ group, action: "delete" })
                          }
                          className="rounded-lg border border-fy-danger px-3 py-2 text-sm font-semibold text-fy-danger"
                        >
                          Delete permanently
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
          {selectedGroup && (
            <section
              aria-labelledby="selected-group-heading"
              className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                    Selected group · {selectedCycle.display_name}
                  </p>
                  <h2
                    id="selected-group-heading"
                    className="mt-1 text-xl font-bold text-fy-text"
                  >
                    {selectedGroup.group_name}
                  </h2>
                  <p className="text-sm text-fy-text-secondary">
                    {selectedGroup.group_email}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {groupCapacity(selectedGroup) !== null &&
                    activeMemberCount(selectedGroup) <
                      (groupCapacity(selectedGroup) ?? 0) &&
                    selectedGroup.is_active && (
                      <button
                        type="button"
                        onClick={() => openAddMember(selectedGroup)}
                        className="rounded-lg bg-fy-brand px-3 py-2 text-sm font-semibold text-white"
                      >
                        Add member
                      </button>
                    )}
                  <BackButton
                    onClick={() => {
                      setSelectedGroupId(null);
                      setArchive(null);
                      writeSelection(selectedCycle.id);
                    }}
                  >
                    Back to groups
                  </BackButton>
                </div>
              </div>
              <div className="mt-4 rounded-lg bg-fy-surface-muted px-3 py-3 text-sm font-semibold text-fy-text">
                Group capacity: {activeMemberCount(selectedGroup)}
                {groupCapacity(selectedGroup) !== null
                  ? ` of ${groupCapacity(selectedGroup)}`
                  : " active members"}
              </div>
              {detailState === "loading" && (
                <p className="mt-5 text-sm text-fy-text-secondary">
                  Loading project and document details...
                </p>
              )}
              {detailState === "error" && (
                <p
                  role="alert"
                  className="mt-5 rounded-lg bg-fy-danger-soft p-3 text-sm text-fy-danger"
                >
                  {detailError ||
                    "The selected group details could not be loaded."}
                </p>
              )}
              {detailState === "ready" && archive && (
                <>
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-lg bg-fy-surface-muted px-3 py-3">
                      <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                        Project title
                      </p>
                      <p className="mt-1 text-sm font-semibold text-fy-text">
                        {display(
                          archive.project?.title || archive.project_title,
                        )}
                      </p>
                    </div>
                    <div className="rounded-lg bg-fy-surface-muted px-3 py-3">
                      <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                        Supervisor
                      </p>
                      <p className="mt-1 text-sm font-semibold text-fy-text">
                        {display(archive.supervisor?.name)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-fy-surface-muted px-3 py-3">
                      <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                        Requirements
                      </p>
                      <p className="mt-1 text-sm font-semibold text-fy-text">
                        {archive.requirements.length}
                      </p>
                    </div>
                  </div>
                  <h3 className="mt-6 text-lg font-bold text-fy-text">
                    Members
                  </h3>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {archive.members.length ? (
                      archive.members.map((member) => (
                        <div
                          key={member.id}
                          className="rounded-lg border border-fy-border px-3 py-2"
                        >
                          <strong className="text-sm">{member.name}</strong>
                          <p className="text-xs text-fy-text-secondary">
                            {member.designation || "Member"} ·{" "}
                            {member.registration_number || "No registration"} ·{" "}
                            {member.email || "No email"}
                          </p>
                        </div>
                      ))
                    ) : (
                      <p className="text-sm text-fy-text-secondary">
                        No members assigned.
                      </p>
                    )}
                  </div>
                  <section className="mt-6 rounded-lg border border-fy-border bg-fy-brand-soft p-4" aria-labelledby="collaboration-credentials-heading">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 id="collaboration-credentials-heading" className="text-lg font-bold text-fy-text">Pending collaboration password resets</h3>
                        <p className="mt-1 max-w-2xl text-sm text-fy-text-secondary">Members create and verify their own collaboration identity password in the Student portal. This admin area is restricted to requested resets only.</p>
                      </div>
                    </div>
                    {collaborationState === "loading" && <p className="mt-3 text-sm text-fy-text-secondary">Loading collaboration credential status...</p>}
                    {collaborationState === "error" && <p role="alert" className="mt-3 rounded-lg bg-fy-danger-soft p-3 text-sm text-fy-danger">{collaborationError}</p>}
                    {collaborationState === "ready" && !collaborationCredentials?.channel_id && <p className="mt-3 rounded-lg border border-dashed border-fy-border bg-fy-surface px-3 py-3 text-sm text-fy-text-secondary">The collaboration channel will be created after a supervisor is assigned.</p>}
                    {collaborationState === "ready" && collaborationCredentials?.channel_id && collaborationCredentials.members.every((credential) => !credential.reset_requested) && <p className="mt-3 rounded-lg border border-dashed border-fy-border bg-fy-surface px-3 py-3 text-sm text-fy-text-secondary">No pending collaboration password reset requests.</p>}
                    {collaborationState === "ready" && collaborationCredentials?.channel_id && collaborationCredentials.members.some((credential) => credential.reset_requested) && <div className="mt-3 grid gap-2">
                      {collaborationCredentials.members.filter((credential) => credential.reset_requested).map((credential) => <div id={`collaboration-reset-member-${credential.member_id}`} key={credential.member_id} className="flex scroll-mt-6 flex-wrap items-center justify-between gap-3 rounded-lg border border-fy-border bg-fy-surface px-3 py-3">
                        <div><strong className="text-sm text-fy-text">{credential.name}</strong><p className="text-xs text-fy-text-secondary">{credential.registration_number} Â· {credential.password_set ? "Password configured" : "Password not configured"}{credential.reset_requested ? " Â· Reset requested" : ""}</p></div>
                        <div className="flex items-center gap-2"><StatusBadge status="RESET REQUESTED" /><button type="button" disabled={collaborationBusyMemberId !== null} onClick={() => void resetCollaborationCredential(credential)} className="rounded-lg border border-fy-brand px-3 py-2 text-xs font-semibold text-fy-brand">{collaborationBusyMemberId === credential.member_id ? "Removing..." : "Remove old password"}</button></div>
                      </div>)}
                    </div>}
                    {collaborationError && collaborationState === "ready" && <p role="alert" className="mt-3 rounded-lg bg-fy-danger-soft p-3 text-sm text-fy-danger">{collaborationError}</p>}
                  </section>
                  <h3 className="mt-6 text-lg font-bold text-fy-text">
                    Requirements, submissions, versions, and review history
                  </h3>
                  {!archive.requirements.length ? (
                    <p className="mt-2 rounded-lg border border-dashed border-fy-border p-4 text-sm text-fy-text-secondary">
                      No document requirements are configured for this cycle and
                      group.
                    </p>
                  ) : (
                    <div className="mt-2 grid gap-3">
                      {archive.requirements.map((requirement) => (
                        <article
                          key={requirement.id}
                          className="rounded-lg border border-fy-border p-4"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div>
                              <h4 className="font-semibold text-fy-text">
                                {requirement.requirement_name}
                              </h4>
                              <p className="text-xs text-fy-text-secondary">
                                {requirement.requirement_section || "Other"} ·{" "}
                                {requirement.is_required
                                  ? "Required"
                                  : "Optional"}
                              </p>
                            </div>
                            <StatusBadge status={requirement.current_status} />
                          </div>
                          <p className="mt-3 text-sm">
                            <strong>Submission:</strong>{" "}
                            {requirement.submitted_file_name || "Not submitted"}
                            {requirement.submitted_at
                              ? ` · ${new Date(requirement.submitted_at).toLocaleString()}`
                              : ""}
                          </p>
                          <p className="mt-1 text-sm">
                            <strong>Versions:</strong>{" "}
                            {requirement.versions.length
                              ? requirement.versions
                                  .map(
                                    (version) =>
                                      `v${version.version_number} ${version.original_filename}`,
                                  )
                                  .join(", ")
                              : "None"}
                          </p>
                          {requirement.review_history.length ? (
                            <div className="mt-3 border-t border-fy-border pt-3">
                              <strong className="text-sm">
                                Review history
                              </strong>
                              <div className="mt-2 grid gap-2">
                                {requirement.review_history.map((event) => (
                                  <div key={event.id} className="text-sm">
                                    <StatusBadge status={event.status} /> ·{" "}
                                    {event.reviewer?.name || "Not assigned"}
                                    {event.reviewed_at
                                      ? ` · ${new Date(event.reviewed_at).toLocaleString()}`
                                      : ""}
                                    {event.comment ? (
                                      <p className="mt-1 whitespace-pre-wrap text-fy-text-secondary">
                                        {event.comment}
                                      </p>
                                    ) : null}
                                  </div>
                                ))}
                              </div>
                            </div>
                          ) : (
                            <p className="mt-3 text-sm text-fy-text-secondary">
                              No review history recorded.
                            </p>
                          )}
                        </article>
                      ))}
                    </div>
                  )}
                </>
              )}
            </section>
          )}
        </section>
      )}
      {approvalTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="group-approval-heading"
          className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
        >
          <form
            onSubmit={approveGroup}
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
          >
            <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
              Group signup review
            </p>
            <h2
              id="group-approval-heading"
              className="mt-1 text-xl font-bold text-fy-text"
            >
              {approvalTarget.is_active
                ? approvalTarget.group_name_assigned
                  ? "Edit official group name"
                  : "Assign official group name"
                : "Approve group access"}
            </h2>
            <p className="mt-2 text-sm text-fy-text-secondary">
              {approvalTarget.is_active
                ? "This name is shown consistently across the group, supervisor, and archive portals."
                : "Assign the official group name. The shared group account stays unable to log in until you approve it."}
            </p>
            <div className="mt-5 grid gap-1 text-sm font-semibold text-fy-text">
              <label htmlFor="official-group-name">Official group name</label>
              <input
                id="official-group-name"
                required
                autoFocus
                value={approvalName}
                onChange={(event) => setApprovalName(event.target.value)}
                placeholder="e.g. Team Phoenix"
                maxLength={255}
                className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2.5 font-normal outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
              />
            </div>
            {approvalError && (
              <p
                role="alert"
                className="mt-4 rounded-lg bg-fy-danger-soft px-3 py-2 text-sm text-fy-danger"
              >
                {approvalError}
              </p>
            )}
            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                disabled={approvalBusy}
                onClick={() => setApprovalTarget(null)}
                className="rounded-lg border border-fy-border px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={approvalBusy}
                className="rounded-lg bg-fy-brand px-4 py-2 text-sm font-semibold text-white"
              >
                {approvalBusy
                  ? "Saving…"
                  : approvalTarget.is_active
                    ? "Save group name"
                    : "Approve group"}
              </button>
            </div>
          </form>
        </div>
      )}
      {confirm && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="group-confirm-heading"
          className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
        >
          <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="group-confirm-heading" className="text-lg font-bold">
              {confirm.action === "delete"
                ? "Confirm permanent deletion"
                : confirm.action === "reject"
                  ? "Reject group signup"
                  : "Confirm deactivation"}
            </h2>
            <p className="mt-2 text-sm text-[#60716b]">
              {confirm.action === "delete"
                ? `Permanently delete ${confirm.group.group_name}? This cannot be undone.`
                : confirm.action === "reject"
                  ? `Reject ${confirm.group.group_name}'s signup? The group will not be able to log in.`
                  : `Deactivate ${confirm.group.group_name}?`}
            </p>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                disabled={busy}
                onClick={() => setConfirm(null)}
                className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void mutate()}
                className={`rounded-lg px-3 py-2 text-sm font-semibold text-white ${confirm.action === "delete" || confirm.action === "reject" ? "bg-fy-danger" : "bg-fy-brand"}`}
              >
                {busy ? "Saving…" : "Confirm"}
              </button>
            </div>
          </div>
        </div>
      )}
      {memberTarget && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="add-member-heading"
          className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
        >
          <form
            onSubmit={addMember}
            className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                  Group member details
                </p>
                <h2
                  id="add-member-heading"
                  className="mt-1 text-xl font-bold text-fy-text"
                >
                  Add member to {memberTarget.group_name}
                </h2>
                <p className="mt-2 text-sm text-fy-text-secondary">
                  Add the member’s details within the cycle limit. The group is
                  the only portal account.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setMemberTarget(null)}
                disabled={memberBusy}
                className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold"
              >
                Close
              </button>
            </div>
            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              {memberFormField(
                "full_name",
                "Member full name",
                "text",
                "Full name",
              )}
              {memberFormField(
                "registration_number",
                "Registration number",
                "text",
                "e.g. 23108170",
              )}
              {memberFormField(
                "email",
                "Member email",
                "email",
                "member@szabist-isb.pk",
              )}
            </div>
            {memberError && (
              <p
                role="alert"
                className="mt-4 rounded-lg bg-fy-danger-soft px-3 py-2 text-sm text-fy-danger"
              >
                {memberError}
              </p>
            )}
            <div className="mt-5 rounded-lg bg-fy-brand-soft px-3 py-3 text-xs text-fy-text-secondary">
               The group still uses one shared portal account, but every member
               gets a separate collaboration password from the panel above.
            </div>
            <div className="mt-5 flex justify-end gap-3">
              <button
                type="button"
                disabled={memberBusy}
                onClick={() => setMemberTarget(null)}
                className="rounded-lg border border-fy-border px-4 py-2 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={memberBusy}
                className="rounded-lg bg-fy-brand px-4 py-2 text-sm font-semibold text-white"
              >
                {memberBusy ? "Adding member…" : "Add member to group"}
              </button>
            </div>
          </form>
        </div>
      )}
    </section>
  );
}
