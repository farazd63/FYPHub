import { FormEvent, useEffect, useMemo, useState } from "react";
import { StatusBadge } from "./ui";
import { ModalPortal } from "./ui/ModalPortal";
import { groupDisplayLabel, sortCyclesDesc } from "./lib/displayLabels";

type Cycle = {
  id: number;
  code: string;
  display_name: string;
  academic_year?: number | null;
  session?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
type Member = {
  id: number;
  full_name: string;
  registration_number: string;
  email: string | null;
  designation?: string;
  is_creator?: boolean;
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
  created_at?: string | null;
  updated_at?: string | null;
  last_activity_at?: string | null;
  supervisor_assignment?: { assigned_at?: string | null } | null;
  assignment?: { assigned_at?: string | null } | null;
  min_group_size?: number | null;
  max_group_size?: number | null;
  group_policy?: { min_group_size: number; max_group_size: number } | null;
  project?: { title?: string | null; updated_at?: string | null } | null;
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
    is_creator?: boolean;
    is_active?: boolean;
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
type MemberEditForm = MemberForm & {
  designation: "LEADER" | "MEMBER";
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

const naturalAscending = (left: string, right: string) =>
  left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" });

const groupNumberForSort = (group: Group) => {
  const explicitNumber = Number(group.group_number);
  if (Number.isFinite(explicitNumber)) return explicitNumber;
  const parsedNumber = group.group_name.match(/(?:group|team)\s+(\d+)/i)?.[1];
  return parsedNumber ? Number(parsedNumber) : Number.POSITIVE_INFINITY;
};

const sortGroupsAscending = (groups: readonly Group[]) =>
  [...groups].sort((left, right) =>
    groupNumberForSort(left) - groupNumberForSort(right) ||
    naturalAscending(left.group_name, right.group_name) ||
    left.id - right.id,
  );

type SortableMember = {
  id: number;
  registration_number?: string | null;
  full_name?: string | null;
  name?: string | null;
};

function sortMembersAscending<T extends SortableMember>(members: readonly T[]) {
  return [...members].sort((left, right) => {
    const leftRegistration = left.registration_number?.trim() || "";
    const rightRegistration = right.registration_number?.trim() || "";
    if (leftRegistration && !rightRegistration) return -1;
    if (!leftRegistration && rightRegistration) return 1;
    return (
      naturalAscending(leftRegistration, rightRegistration) ||
      naturalAscending(left.full_name || left.name || "", right.full_name || right.name || "") ||
      left.id - right.id
    );
  });
}

export function groupsForCycle(groups: Group[], selectedCycleId: number) {
  return sortGroupsAscending(
    groups.filter((group) => group.academic_cycle_id === selectedCycleId),
  );
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
  const [memberManagerTarget, setMemberManagerTarget] = useState<Group | null>(null);
  const [memberDrafts, setMemberDrafts] = useState<Record<number, MemberEditForm>>({});
  const [memberSaveBusyId, setMemberSaveBusyId] = useState<number | null>(null);
  const [memberRemoveBusyId, setMemberRemoveBusyId] = useState<number | null>(null);
  const [memberManagerError, setMemberManagerError] = useState("");
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
        const available = sortCyclesDesc(Array.isArray(body) ? (body as Cycle[]) : []);
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
    setApprovalError("");
  };
  const openAddMember = (group: Group) => {
    setMemberTarget(group);
    setMemberError("");
    setMemberForm({ full_name: "", registration_number: "", email: "" });
  };

  const memberEditDraft = (member: Member): MemberEditForm => ({
    full_name: member.full_name,
    registration_number: member.registration_number,
    email: member.email || "",
    designation: member.designation === "LEADER" ? "LEADER" : "MEMBER",
  });

  const openMemberManager = (group: Group) => {
    const activeMembers = group.members.filter((member) => member.is_active !== false);
    setMemberManagerTarget(group);
    setMemberManagerError("");
    setMemberDrafts(
      Object.fromEntries(
        activeMembers.map((member) => [member.id, memberEditDraft(member)]),
      ) as Record<number, MemberEditForm>,
    );
  };

  const closeMemberManager = () => {
    setMemberManagerTarget(null);
    setMemberManagerError("");
    setMemberSaveBusyId(null);
    setMemberRemoveBusyId(null);
  };

  const applyMemberUpdates = (groupId: number, updates: Member[]) => {
    const updateById = new Map(updates.map((member) => [member.id, member]));
    const applyToGroup = (group: Group) =>
      group.id !== groupId
        ? group
        : {
            ...group,
            members: group.members.map((member) => updateById.get(member.id) || member),
            member_count: group.members.filter(
              (member) => (updateById.get(member.id) || member).is_active !== false,
            ).length,
          };
    setGroups((current) => current.map(applyToGroup));
    setMemberManagerTarget((current) => (current ? applyToGroup(current) : current));
    setArchive((current) => {
      if (!current || current.group_id !== groupId) return current;
      return {
        ...current,
        members: current.members.map((member) => {
          const update = updateById.get(member.id);
          return update
            ? {
                ...member,
                name: update.full_name,
                registration_number: update.registration_number,
                email: update.email,
                designation: update.designation,
                is_creator: update.is_creator,
                is_active: update.is_active,
              }
            : member;
        }),
      };
    });
    setMemberDrafts((current) => {
      const next = { ...current };
      updates.forEach((member) => {
        next[member.id] = memberEditDraft(member);
      });
      return next;
    });
  };

  const saveMember = async (memberId: number) => {
    if (!memberManagerTarget || memberSaveBusyId !== null || memberRemoveBusyId !== null) return;
    const draft = memberDrafts[memberId];
    if (!draft) return;
    setMemberSaveBusyId(memberId);
    setMemberManagerError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${memberManagerTarget.id}/members/${memberId}`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(draft),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(errorText(body, "The group member could not be updated."));
      const updates = Array.isArray(body.updated_members)
        ? (body.updated_members as Member[])
        : [body.member as Member];
      applyMemberUpdates(memberManagerTarget.id, updates);
      setCollaborationReload((value) => value + 1);
      setNotice(`${body.member?.full_name || draft.full_name} was updated in the group.`);
    } catch (error) {
      setMemberManagerError(
        error instanceof Error ? error.message : "The group member could not be updated.",
      );
    } finally {
      setMemberSaveBusyId(null);
    }
  };

  const removeMember = async (member: Member) => {
    if (!memberManagerTarget || memberRemoveBusyId !== null || memberSaveBusyId !== null) return;
    if (!window.confirm(`Remove ${member.full_name} from ${groupDisplayLabel(memberManagerTarget, selectedCycle)}? Their historical submissions will be kept, but they will no longer be an active group member.`)) return;
    setMemberRemoveBusyId(member.id);
    setMemberManagerError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${memberManagerTarget.id}/members/${member.id}`,
        { method: "DELETE", credentials: "include" },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(errorText(body, "The group member could not be removed."));
      const updates = [body.member as Member];
      if (body.promoted_member) updates.push(body.promoted_member as Member);
      applyMemberUpdates(memberManagerTarget.id, updates);
      setCollaborationReload((value) => value + 1);
      setNotice(`${member.full_name} was removed from the group. Historical records were kept.`);
    } catch (error) {
      setMemberManagerError(
        error instanceof Error ? error.message : "The group member could not be removed.",
      );
    } finally {
      setMemberRemoveBusyId(null);
    }
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
      setCollaborationReload((value) => value + 1);
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
    setApprovalBusy(true);
    setApprovalError("");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/student-groups/${approvalTarget.id}/activate`,
        {
          method: "PATCH",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({}),
        },
      );
      const body = await response.json().catch(() => ({}));
      if (!response.ok)
        throw new Error(errorText(body, "The group could not be approved."));
      setApprovalTarget(null);
      const generatedName = typeof body?.group_name === "string" ? body.group_name : approvalTarget.group_name;
      setNotice(
        `${generatedName} was approved and can now log in with its group credentials.`,
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
            FYP Groups
          </p>
          <h1
            id="student-groups-heading"
            className="text-2xl font-bold tracking-tight"
          >
            {selectedCycle ? "Student groups" : "FYP Cycles"}
          </h1>
          <p className={selectedCycle ? "hidden" : "mt-1 text-sm text-fy-text-secondary"}>
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
                  {cycle.display_name}
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
                <span className="hidden">
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
              <p className="mt-2 text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                Selected cycle
              </p>
              <h2
                id="selected-cycle-heading"
                className="text-xl font-bold text-fy-text"
              >
                {selectedCycle.display_name}
              </h2>
            </div>
            <p className="text-sm font-semibold text-fy-text-secondary">
              {groupState === "ready"
                ? `${groups.length} group${groups.length === 1 ? "" : "s"}`
                : ""}
            </p>
          </div>
          <div
            aria-label="Student groups and selected group details"
            className="grid items-start gap-4"
          >
            {groupState === "loading" && (
              <div className="rounded-xl border border-fy-border bg-fy-surface p-5 text-sm text-fy-text-secondary">
                Loading groups...
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
                No FYP groups are available in the selected cycle.
              </div>
            )}
            {groupState === "ready" && groups.length > 0 && !selectedGroup && (
            <div className="grid gap-4">
              {groups.map((group) => {
                const count = activeMemberCount(group);
                const capacity = groupCapacity(group);
                const activeMembers = sortMembersAscending(
                  group.members.filter((member) => member.is_active !== false),
                );
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
                        <span className="hidden">
                          Group {group.group_number ?? "—"} ·{" "}
                          {selectedCycle.display_name}
                        </span>
                        <h3 className="mt-1 text-lg font-bold text-fy-text">
                          {groupDisplayLabel(group, selectedCycle)}
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
                    {!selectedGroup && <div className="mt-4 overflow-x-auto">
                      <table className="w-full min-w-[900px] text-left text-sm">
                        <thead className="border-b border-fy-border text-xs uppercase tracking-wide text-fy-text-secondary">
                          <tr>
                            <th className="px-2 py-2">Member</th>
                            <th className="px-2 py-2">Registration</th>
                            <th className="px-2 py-2">Email</th>
                            <th className="px-2 py-2">Role</th>
                            <th className="px-2 py-2">Final Project Title</th>
                            <th className="px-2 py-2">Supervisor</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-fy-border">
                          {activeMembers.length ? (
                            activeMembers.map((member) => (
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
                                    "Final title not set"}
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
                    </div>}
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
                            "Approve group"
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
              className="min-w-0 rounded-xl border border-fy-border bg-fy-surface p-5"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="hidden">
                    Selected group · {selectedCycle.display_name}
                  </p>
                  <h2
                    id="selected-group-heading"
                    className="mt-1 text-xl font-bold text-fy-text"
                  >
                    {groupDisplayLabel(selectedGroup, selectedCycle)}
                  </h2>
                  <p className="text-sm text-fy-text-secondary">
                    {selectedGroup.group_email}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => openMemberManager(selectedGroup)}
                    className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold text-fy-brand"
                  >
                    Edit members
                  </button>
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
                  <h3 className="mt-6 text-lg font-bold text-fy-text">Members</h3>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    {sortMembersAscending(
                      archive.members.filter((member) => member.is_active !== false),
                    ).length ? (
                      sortMembersAscending(
                        archive.members.filter((member) => member.is_active !== false),
                      )
                        .map((member) => (
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
                      </div>
                    </div>
                    {collaborationState === "loading" && <p className="mt-3 text-sm text-fy-text-secondary">Loading collaboration credential status...</p>}
                    {collaborationState === "error" && <p role="alert" className="mt-3 rounded-lg bg-fy-danger-soft p-3 text-sm text-fy-danger">{collaborationError}</p>}
                    {collaborationState === "ready" && !collaborationCredentials?.channel_id && <p className="mt-3 rounded-lg border border-dashed border-fy-border bg-fy-surface px-3 py-3 text-sm text-fy-text-secondary">The collaboration channel will be created after a supervisor is assigned.</p>}
                    {collaborationState === "ready" && collaborationCredentials?.channel_id && collaborationCredentials.members.every((credential) => !credential.reset_requested) && <p className="mt-3 rounded-lg border border-dashed border-fy-border bg-fy-surface px-3 py-3 text-sm text-fy-text-secondary">No pending collaboration password reset requests.</p>}
                    {collaborationState === "ready" && collaborationCredentials?.channel_id && collaborationCredentials.members.some((credential) => credential.reset_requested) && <div className="mt-3 grid gap-2">
                      {collaborationCredentials.members.filter((credential) => credential.reset_requested).map((credential) => <div id={`collaboration-reset-member-${credential.member_id}`} key={credential.member_id} className="flex scroll-mt-6 flex-wrap items-center justify-between gap-3 rounded-lg border border-fy-border bg-fy-surface px-3 py-3">
                        <div><strong className="text-sm text-fy-text">{credential.name}</strong><p className="text-xs text-fy-text-secondary">{credential.registration_number} · {credential.password_set ? "Password configured" : "Password not configured"}{credential.reset_requested ? " · Reset requested" : ""}</p></div>
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
          </div>
        </section>
      )}
      {approvalTarget && (
        <ModalPortal>
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
            <p className="hidden text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
              Group signup review
            </p>
            <h2
              id="group-approval-heading"
              className="mt-1 text-xl font-bold text-fy-text"
            >
              {approvalTarget.is_active
                ? "Refresh automatic group name"
                : "Approve group access"}
            </h2>
            <div className="mt-5 rounded-lg border border-fy-border bg-fy-surface px-3 py-3 text-sm">
              <span className="block text-xs font-bold uppercase tracking-wide text-fy-text-secondary">Automatic group name</span>
              <strong className="mt-1 block text-fy-text">{groupDisplayLabel(approvalTarget, selectedCycle)}</strong>
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
                    ? "Refresh name"
                    : "Approve group"}
              </button>
            </div>
            </form>
          </div>
        </ModalPortal>
      )}
      {confirm && (
        <ModalPortal>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="group-confirm-heading"
            className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
          >
            <div className="w-full max-w-md rounded-xl bg-white p-5 shadow-xl">
            <h2 id="group-confirm-heading" className="text-lg font-bold">
              {confirm.action === "delete"
                ? `Delete ${groupDisplayLabel(confirm.group, selectedCycle)}`
                : confirm.action === "reject"
                  ? `Reject ${groupDisplayLabel(confirm.group, selectedCycle)}`
                  : `Deactivate ${groupDisplayLabel(confirm.group, selectedCycle)}`}
            </h2>
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
        </ModalPortal>
      )}
      {memberManagerTarget && (
        <ModalPortal>
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="edit-members-heading"
            className="fixed inset-0 z-50 grid place-items-center bg-[#243746]/35 p-4"
          >
            <div className="max-h-[90vh] w-full max-w-6xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="hidden text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                  Group member management
                </p>
                <h2 id="edit-members-heading" className="mt-1 text-xl font-bold text-fy-text">
                  Edit members in {groupDisplayLabel(memberManagerTarget, selectedCycle)}
                </h2>
              </div>
              <button
                type="button"
                onClick={closeMemberManager}
                disabled={memberSaveBusyId !== null || memberRemoveBusyId !== null}
                className="rounded-lg border border-fy-border px-3 py-2 text-sm font-semibold"
              >
                Close
              </button>
            </div>
            <div className="mt-5 overflow-x-auto rounded-lg border border-fy-border">
              <table className="min-w-[960px] w-full text-left text-sm">
                <thead className="border-b border-fy-border bg-fy-surface-muted text-xs uppercase tracking-wide text-fy-text-secondary">
                  <tr>
                    <th className="px-3 py-3">Full name</th>
                    <th className="px-3 py-3">Registration</th>
                    <th className="px-3 py-3">Email</th>
                    <th className="px-3 py-3">Role</th>
                    <th className="px-3 py-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-fy-border">
                  {sortMembersAscending(
                    memberManagerTarget.members.filter((member) => member.is_active !== false),
                  ).length ? (
                    sortMembersAscending(
                      memberManagerTarget.members.filter((member) => member.is_active !== false),
                    )
                      .map((member) => {
                        const draft = memberDrafts[member.id] || memberEditDraft(member);
                        const rowBusy = memberSaveBusyId === member.id || memberRemoveBusyId === member.id;
                        return (
                          <tr key={member.id}>
                            <td className="px-3 py-3">
                              <input
                                value={draft.full_name}
                                onChange={(event) => setMemberDrafts((current) => ({ ...current, [member.id]: { ...draft, full_name: event.target.value } }))}
                                className="w-full min-w-44 rounded-lg border border-fy-border bg-fy-surface px-3 py-2 outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
                                aria-label={`Full name for ${member.full_name}`}
                              />
                            </td>
                            <td className="px-3 py-3">
                              <input
                                value={draft.registration_number}
                                onChange={(event) => setMemberDrafts((current) => ({ ...current, [member.id]: { ...draft, registration_number: event.target.value } }))}
                                className="w-full min-w-36 rounded-lg border border-fy-border bg-fy-surface px-3 py-2 outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
                                aria-label={`Registration number for ${member.full_name}`}
                              />
                            </td>
                            <td className="px-3 py-3">
                              <input
                                type="email"
                                value={draft.email}
                                onChange={(event) => setMemberDrafts((current) => ({ ...current, [member.id]: { ...draft, email: event.target.value } }))}
                                className="w-full min-w-56 rounded-lg border border-fy-border bg-fy-surface px-3 py-2 outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
                                aria-label={`Email for ${member.full_name}`}
                              />
                            </td>
                            <td className="px-3 py-3">
                              <select
                                value={draft.designation}
                                onChange={(event) => setMemberDrafts((current) => ({ ...current, [member.id]: { ...draft, designation: event.target.value as MemberEditForm["designation"] } }))}
                                className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2 outline-none focus:border-fy-brand focus:ring-2 focus:ring-fy-brand/20"
                                aria-label={`Role for ${member.full_name}`}
                              >
                                <option value="LEADER">Leader</option>
                                <option value="MEMBER">Member</option>
                              </select>
                            </td>
                            <td className="px-3 py-3">
                              <div className="flex flex-wrap gap-2">
                                <button
                                  type="button"
                                  onClick={() => void saveMember(member.id)}
                                  disabled={rowBusy || memberSaveBusyId !== null || memberRemoveBusyId !== null}
                                  className="rounded-lg bg-fy-brand px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
                                >
                                  {memberSaveBusyId === member.id ? "Saving..." : "Save changes"}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => void removeMember(member)}
                                  disabled={rowBusy || memberSaveBusyId !== null || memberRemoveBusyId !== null || memberManagerTarget.members.filter((item) => item.is_active !== false).length <= 1}
                                  title={memberManagerTarget.members.filter((item) => item.is_active !== false).length <= 1 ? "A group must keep at least one active member." : "Remove this member from the group"}
                                  className="rounded-lg border border-fy-danger px-3 py-2 text-xs font-semibold text-fy-danger disabled:opacity-50"
                                >
                                  {memberRemoveBusyId === member.id ? "Removing..." : "Remove member"}
                                </button>
                              </div>
                            </td>
                          </tr>
                        );
                      })
                  ) : (
                    <tr>
                      <td colSpan={5} className="px-3 py-4 text-fy-text-secondary">
                        No active members are assigned to this group.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            {memberManagerError && (
              <p role="alert" className="mt-4 rounded-lg bg-fy-danger-soft px-3 py-2 text-sm text-fy-danger">
                {memberManagerError}
              </p>
            )}
            <div className="mt-5 flex flex-wrap justify-end gap-3">
              {memberManagerTarget.is_active &&
                groupCapacity(memberManagerTarget) !== null &&
                activeMemberCount(memberManagerTarget) < (groupCapacity(memberManagerTarget) ?? 0) && (
                  <button
                    type="button"
                    onClick={() => {
                      const group = memberManagerTarget;
                      closeMemberManager();
                      openAddMember(group);
                    }}
                    disabled={memberSaveBusyId !== null || memberRemoveBusyId !== null}
                    className="rounded-lg bg-fy-brand px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                  >
                    Add new member
                  </button>
                )}
              <button
                type="button"
                onClick={closeMemberManager}
                disabled={memberSaveBusyId !== null || memberRemoveBusyId !== null}
                className="rounded-lg border border-fy-border px-4 py-2 text-sm font-semibold"
              >
                Done
              </button>
            </div>
            </div>
          </div>
        </ModalPortal>
      )}
      {memberTarget && (
        <ModalPortal>
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
                <p className="hidden text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                  Group member details
                </p>
                <h2
                  id="add-member-heading"
                  className="mt-1 text-xl font-bold text-fy-text"
                >
                  Add member to {groupDisplayLabel(memberTarget, selectedCycle)}
                </h2>
                <p className="hidden mt-2 text-sm text-fy-text-secondary">
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
            <div className="hidden mt-5 rounded-lg bg-fy-brand-soft px-3 py-3 text-xs text-fy-text-secondary">
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
        </ModalPortal>
      )}
    </section>
  );
}
