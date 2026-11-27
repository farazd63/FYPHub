import { useCallback, useEffect, useMemo, useState } from "react";
import { StatusBadge } from "./ui";
import { AdminAddButton } from "./ui/AdminAddButton";
import { appPathname } from "./platform-path";
import { groupDisplayLabel, sortCyclesDesc, sortGroupsDesc } from "./lib/displayLabels";
import "./admin-document-archive.css";

type Cycle = {
  id: number;
  code: string;
  name: string;
  display_name: string;
  academic_year?: number | string | null;
  session?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  group_count?: number;
  requirement_count?: number;
  submission_count?: number;
};
type Requirement = {
  id: number;
  title: string;
  description?: string | null;
  academic_cycle_id: number;
  due_at: string;
  module: string;
  allowed_file_types: string[];
  max_file_size_mb: number;
  is_required: boolean;
  status: string;
  submission_count?: number;
};
type Member = {
  id: number;
  name: string;
  registration_number?: string | null;
  email?: string | null;
  designation?: string | null;
};
type Person = {
  id: number;
  name: string;
  email?: string | null;
  registration_number?: string | null;
} | null;
type Group = {
  id: number;
  group_id: number;
  cycle_id: number;
  cycle_name: string;
  group_code: string;
  group_number?: number | string | null;
  group_name?: string | null;
  project_title?: string | null;
  project?: {
    id: number;
    title?: string | null;
    status?: string | null;
    updated_at?: string | null;
  } | null;
  members: Member[];
  supervisor: Person;
  completion_percentage: number;
  last_submission_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  last_activity_at?: string | null;
  requirement_count: number;
  submitted_requirement_count: number;
  status: string;
  requirements?: ArchiveRow[];
  total_requirements?: number;
  filtered_requirements?: number;
};
type Version = {
  id: number;
  version_number: number;
  original_filename: string;
  mime_type: string;
  file_size: number;
  uploaded_at: string;
  uploaded_by_id?: number | null;
  view_url?: string | null;
  download_url?: string | null;
};
type ReviewEvent = {
  id: number;
  status: string;
  reviewer?: Person;
  reviewed_at?: string | null;
  comment?: string | null;
  version_id?: number | null;
};
type ArchiveRow = {
  id: number;
  cycle_id: number;
  cycle_name: string;
  group_id: number;
  group_code: string;
  group_number?: number | string | null;
  group_name?: string | null;
  project_id?: number | null;
  project_title?: string | null;
  requirement_section_id?: number | null;
  requirement_section: string;
  requirement_id: number;
  requirement_name: string;
  student_id?: number | null;
  student_name?: string | null;
  registration_number?: string | null;
  uploader_id?: number | null;
  uploader_name?: string | null;
  submission_id?: number | null;
  submitted_file_name?: string | null;
  submitted_at?: string | null;
  version_number?: number | null;
  current_status: string;
  reviewer?: Person;
  reviewer_name?: string | null;
  reviewed_at?: string | null;
  reviewer_comments?: string | null;
  latest_version_id?: number | null;
  view_url?: string | null;
  download_url?: string | null;
  versions: Version[];
  review_history: ReviewEvent[];
  requirement_status: string;
  is_required: boolean;
  due_at: string;
};
type Archive = Group & {
  requirements: ArchiveRow[];
  total_requirements: number;
  filtered_requirements: number;
  member_user_ids: number[];
};
type RequirementGroupRecord = {
  group: Group;
  row: ArchiveRow | null;
};
type RequirementStatusFilter =
  | "ALL"
  | "SUBMITTED"
  | "MISSING"
  | "UNDER_REVIEW"
  | "ACCEPTED"
  | "CHANGES_REQUESTED";
const requirementStatusOptions: Array<{
  value: RequirementStatusFilter;
  label: string;
}> = [
  { value: "ALL", label: "All groups" },
  { value: "SUBMITTED", label: "Submitted" },
  { value: "MISSING", label: "Missing" },
  { value: "UNDER_REVIEW", label: "Under review" },
  { value: "ACCEPTED", label: "Accepted" },
  { value: "CHANGES_REQUESTED", label: "Needs changes" },
];
const fileFormatOptions: Array<{
  value: string;
  label: string;
  extensions: string[];
}> = [
  { value: "pdf", label: "PDF", extensions: ["pdf"] },
  { value: "word", label: "Word", extensions: ["doc", "docx"] },
  {
    value: "video",
    label: "Video",
    extensions: ["mp4", "mov", "avi", "mkv", "webm"],
  },
  { value: "ppt", label: "PPT", extensions: ["ppt", "pptx"] },
  { value: "audio", label: "Audio", extensions: ["mp3", "wav", "m4a", "ogg"] },
  { value: "txt", label: "TXT", extensions: ["txt"] },
  { value: "zip", label: "ZIP", extensions: ["zip"] },
];

const formatLabels = (extensions: string[]) =>
  fileFormatOptions
    .filter((option) => option.extensions.some((extension) => extensions.includes(extension)))
    .map((option) => option.label);

const FIELD_MESSAGES: Record<string, Record<string, string>> = {
  max_file_size_mb: {
    greater_than_equal: "Max size must be at least 1 MB.",
    less_than_equal: "Max size must be at most 100 MB.",
    int_parsing: "Max size must be a whole number of megabytes.",
    missing: "Max size is required.",
  },
  title: {
    missing: "Requirement name is required.",
    string_too_short: "Requirement name is required.",
  },
  due_at: {
    missing: "Deadline is required.",
    datetime_parsing: "Deadline must be a valid date and time.",
  },
  academic_cycle_id: { missing: "Academic cycle is required." },
};

const errorText = (body: unknown, fallback: string) => {
  if (!body || typeof body !== "object") return fallback;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && !Array.isArray(detail)) {
    const payload = detail as {
      message?: unknown;
      fields?: Array<{ path?: string; code?: string }>;
    };
    if (Array.isArray(payload.fields) && payload.fields.length) {
      const parts = payload.fields
        .map((field) => {
          const path = (field.path || "").split(".").pop() || "";
          const mapped = FIELD_MESSAGES[path]?.[field.code || ""];
          if (mapped) return mapped;
          if (path && field.code)
            return `${path}: ${field.code.replaceAll("_", " ")}`;
          return "";
        })
        .filter(Boolean);
      if (parts.length) return parts.join(" ");
    }
    if (typeof payload.message === "string" && payload.message.trim())
      return payload.message;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") return "";
        const entry = item as { loc?: unknown[]; msg?: unknown };
        const field = Array.isArray(entry.loc)
          ? entry.loc.filter((part) => part !== "body").join(".")
          : "";
        const msg = typeof entry.msg === "string" ? entry.msg : "";
        return field && msg ? `${field}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (parts.length) return parts.join(" ");
  }
  return fallback;
};

const dateText = (value?: string | null) =>
  value ? new Date(value).toLocaleString() : "Not submitted";
const rowStatus = (row: ArchiveRow | null) => row?.current_status || "NOT_SUBMITTED";
const isMissingStatus = (status: string) =>
  status === "NOT_SUBMITTED" || status === "CLOSED";
const isChangesRequestedStatus = (status: string) =>
  status === "CHANGES_REQUESTED" || status === "REJECTED";
const dateTimeInputValue = (value?: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60_000).toISOString().slice(0, 16);
};
const display = (value?: string | null, fallback = "Not assigned") =>
  value && value.trim() ? value : fallback;
async function readJson(response: Response) {
  return response.json().catch(() => ({})) as Promise<unknown>;
}

const archiveRouteFromPath = () => {
  const match = appPathname().match(
    /^\/admin\/document-requirements\/cycles\/(\d+)\/groups\/(\d+)$/,
  );
  if (!match) return null;
  const cycleId = Number(match[1]);
  const groupId = Number(match[2]);
  return Number.isInteger(cycleId) && cycleId > 0 && Number.isInteger(groupId) && groupId > 0
    ? { cycleId, groupId }
    : null;
};

export function AdminDocumentArchive({ api }: { api: string }) {
  const archiveRoute = archiveRouteFromPath();
  const detailOnly = archiveRoute !== null;
  const [cycles, setCycles] = useState<Cycle[]>([]);
  const [selectedCycleId, setSelectedCycleId] = useState<number | null>(
    archiveRoute?.cycleId ?? null,
  );
  const [groups, setGroups] = useState<Group[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(
    archiveRoute?.groupId ?? null,
  );
  const [archive, setArchive] = useState<Archive | null>(null);
  const [cycleState, setCycleState] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [requirementsState, setRequirementsState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [selectedRequirementId, setSelectedRequirementId] = useState<number | null>(null);
  const [requirementStatusFilter, setRequirementStatusFilter] =
    useState<RequirementStatusFilter>("ALL");
  const [groupState, setGroupState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [detailState, setDetailState] = useState<
    "idle" | "loading" | "ready" | "error"
  >("idle");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingRequirementId, setEditingRequirementId] = useState<number | null>(
    null,
  );
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [deadline, setDeadline] = useState("");
  const [module, setModule] = useState("General");
  const [formats, setFormats] = useState<string[]>(["pdf"]);
  const [maxSize, setMaxSize] = useState("10");
  const [required, setRequired] = useState(true);

  const selectedCycle = useMemo(
    () => cycles.find((cycle) => cycle.id === selectedCycleId) || null,
    [cycles, selectedCycleId],
  );
  const selectedRequirement = useMemo(
    () => requirements.find((requirement) => requirement.id === selectedRequirementId) || null,
    [requirements, selectedRequirementId],
  );
  const selectedRequirementRows = useMemo<RequirementGroupRecord[]>(
    () => selectedRequirementId === null
      ? []
      : groups.map((group) => ({
          group,
          row: group.requirements?.find((item) => item.requirement_id === selectedRequirementId) || null,
        })),
    [groups, selectedRequirementId],
  );
  const selectedRequirementStats = useMemo(() => {
    const statuses = selectedRequirementRows.map(({ row }) => rowStatus(row));
    return {
      total: statuses.length,
      submitted: statuses.filter((status) => !isMissingStatus(status)).length,
      missing: statuses.filter(isMissingStatus).length,
      underReview: statuses.filter((status) => status === "UNDER_REVIEW").length,
      accepted: statuses.filter((status) => status === "ACCEPTED").length,
      changesRequested: statuses.filter(isChangesRequestedStatus).length,
    };
  }, [selectedRequirementRows]);
  const visibleRequirementRows = useMemo(
    () => selectedRequirementRows.filter(({ row }) => {
      const status = rowStatus(row);
      if (requirementStatusFilter === "ALL") return true;
      if (requirementStatusFilter === "SUBMITTED") return !isMissingStatus(status);
      if (requirementStatusFilter === "MISSING") return isMissingStatus(status);
      if (requirementStatusFilter === "CHANGES_REQUESTED") return isChangesRequestedStatus(status);
      return status === requirementStatusFilter;
    }),
    [requirementStatusFilter, selectedRequirementRows],
  );

  const loadCycles = useCallback(async () => {
    setCycleState("loading");
    try {
      const response = await fetch(
        `${api}/api/v1/admin/document-archive/cycles`,
        { credentials: "include" },
      );
      const body = await readJson(response);
      if (!response.ok)
        throw new Error(
          errorText(body, "Academic cycles could not be loaded."),
        );
      setCycles(sortCyclesDesc(Array.isArray(body) ? (body as Cycle[]) : []));
      setCycleState("ready");
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "Academic cycles could not be loaded.",
      );
      setCycleState("error");
    }
  }, [api]);

  const loadRequirements = useCallback(
    async (cycleId: number) => {
      setRequirementsState("loading");
      try {
        const response = await fetch(`${api}/api/v1/document-requirements`, {
          credentials: "include",
        });
        const body = await readJson(response);
        if (!response.ok)
          throw new Error(
            errorText(body, "Document requirements could not be loaded."),
          );
        const rows = Array.isArray(body) ? (body as Requirement[]) : [];
        setRequirements(
          rows.filter((requirement) => requirement.academic_cycle_id === cycleId),
        );
        setRequirementsState("ready");
      } catch (error) {
        setRequirements([]);
        setNotice(
          error instanceof Error
            ? error.message
            : "Document requirements could not be loaded.",
        );
        setRequirementsState("error");
      }
    },
    [api],
  );

  const loadGroups = useCallback(
    async (cycleId: number) => {
      setGroupState("loading");
      try {
        const response = await fetch(
          `${api}/api/v1/admin/document-archive/cycles/${cycleId}/groups`,
          { credentials: "include" },
        );
        const body = await readJson(response);
        if (!response.ok)
          throw new Error(errorText(body, "Groups could not be loaded."));
        setGroups(
          sortGroupsDesc(
            body &&
              typeof body === "object" &&
              Array.isArray((body as { groups?: unknown }).groups)
              ? (body as { groups: Group[] }).groups
              : [],
          ),
        );
        setGroupState("ready");
      } catch (error) {
        setGroups([]);
        setNotice(
          error instanceof Error
            ? error.message
            : "Groups could not be loaded.",
        );
        setGroupState("error");
      }
    },
    [api],
  );

  const loadArchive = useCallback(
    async (cycleId: number, groupId: number) => {
      setDetailState("loading");
      try {
        const response = await fetch(
          `${api}/api/v1/admin/document-archive/cycles/${cycleId}/groups/${groupId}`,
          { credentials: "include" },
        );
        const body = await readJson(response);
        if (!response.ok)
          throw new Error(
            errorText(body, "The group archive could not be loaded."),
          );
        setArchive(
          (body && typeof body === "object" && "group" in body
            ? (body as { group: Archive }).group
            : body) as Archive,
        );
        setDetailState("ready");
      } catch (error) {
        setArchive(null);
        setNotice(
          error instanceof Error
            ? error.message
            : "The group archive could not be loaded.",
        );
        setDetailState("error");
      }
    },
    [api],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadCycles();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadCycles]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (detailOnly) return;
      if (selectedCycleId === null) {
        setGroups([]);
        setSelectedGroupId(null);
        setSelectedRequirementId(null);
        setRequirementStatusFilter("ALL");
        setArchive(null);
        setGroupState("idle");
        setDetailState("idle");
        return;
      }
      setSelectedGroupId(null);
      setSelectedRequirementId(null);
      setRequirementStatusFilter("ALL");
      setArchive(null);
      void loadGroups(selectedCycleId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [detailOnly, loadGroups, selectedCycleId]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (detailOnly || selectedCycleId === null) {
        setRequirements([]);
        setRequirementsState("idle");
        return;
      }
      void loadRequirements(selectedCycleId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [detailOnly, loadRequirements, selectedCycleId]);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (selectedCycleId !== null && selectedGroupId !== null)
        void loadArchive(selectedCycleId, selectedGroupId);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadArchive, selectedCycleId, selectedGroupId]);
  const selectCycle = (value: string) => {
    setNotice("");
    setSelectedGroupId(null);
    setSelectedRequirementId(null);
    setRequirementStatusFilter("ALL");
    setArchive(null);
    setSelectedCycleId(value ? Number(value) : null);
  };
  const selectRequirement = (requirementId: number) => {
    setNotice("");
    setRequirementStatusFilter("ALL");
    setSelectedRequirementId((current) => current === requirementId ? null : requirementId);
  };
  const openGroup = (groupId: number) => {
    setNotice("");
    if (selectedCycleId === null) return;
    window.location.assign(
      `/admin/document-requirements/cycles/${selectedCycleId}/groups/${groupId}`,
    );
  };
  const download = async (
    row: ArchiveRow,
    version = row.latest_version_id
      ? row.versions.find((item) => item.id === row.latest_version_id)
      : row.versions[row.versions.length - 1],
  ) => {
    if (!version?.download_url) return;
    setBusy(`download-${version.id}`);
    setNotice("");
    try {
      const response = await fetch(`${api}${version.download_url}`, {
        credentials: "include",
      });
      if (!response.ok)
        throw new Error("The document could not be downloaded.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = version.original_filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : "The document could not be downloaded.",
      );
    } finally {
      setBusy(null);
    }
  };

  const resetRequirementForm = () => {
    setEditingRequirementId(null);
    setTitle("");
    setDescription("");
    setDeadline("");
    setModule("General");
    setFormats(["pdf"]);
    setMaxSize("10");
    setRequired(true);
  };

  const editRequirement = (requirement: Requirement) => {
    setEditingRequirementId(requirement.id);
    setTitle(requirement.title);
    setDescription(requirement.description || "");
    setDeadline(dateTimeInputValue(requirement.due_at));
    setModule(requirement.module || "General");
    setFormats(requirement.allowed_file_types || []);
    setMaxSize(String(requirement.max_file_size_mb));
    setRequired(requirement.is_required);
    setShowCreate(true);
    setNotice("");
  };

  const openCreateForm = () => {
    resetRequirementForm();
    setShowCreate(true);
    setNotice("");
  };

  const toggleCreateForm = () => {
    if (showCreate) {
      setShowCreate(false);
      resetRequirementForm();
      return;
    }
    openCreateForm();
  };

  const saveRequirement = async (publish: boolean) => {
    if (
      selectedCycleId === null ||
      !title.trim() ||
      !deadline ||
      !formats.length
    ) {
      setNotice(
        "Select a cycle, provide a title and deadline, and choose at least one file format.",
      );
      return;
    }
    const editing = editingRequirementId !== null;
    setBusy(editing ? `edit-${editingRequirementId}` : "create");
    setNotice("");
    try {
      const response = await fetch(
        editing
          ? `${api}/api/v1/document-requirements/${editingRequirementId}`
          : `${api}/api/v1/document-requirements`,
        {
        method: editing ? "PATCH" : "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim() || null,
          academic_cycle_id: selectedCycleId,
          module: module.trim() || "General",
          allowed_file_types: formats,
          max_file_size_mb: Number(maxSize),
          is_required: required,
          due_at: new Date(deadline).toISOString(),
        }),
        },
      );
      const body = await readJson(response);
      if (!response.ok)
        throw new Error(
          errorText(
            body,
            editing
              ? "The requirement could not be updated."
              : "The requirement could not be created.",
          ),
        );
      if (
        !editing &&
        publish &&
        body &&
        typeof body === "object" &&
        typeof (body as { id?: unknown }).id === "number"
      ) {
        const publishResponse = await fetch(
          `${api}/api/v1/document-requirements/${(body as { id: number }).id}/publish`,
          { method: "POST", credentials: "include" },
        );
        if (!publishResponse.ok)
          throw new Error(
            errorText(
              await readJson(publishResponse),
              "The requirement was created but could not be published.",
            ),
          );
      }
      resetRequirementForm();
      setShowCreate(false);
      setNotice(
        editing
          ? "Requirement updated."
          : publish
            ? "Requirement published."
            : "Requirement saved as draft.",
      );
      await loadCycles();
      await loadRequirements(selectedCycleId);
      await loadGroups(selectedCycleId);
      if (selectedGroupId !== null)
        await loadArchive(selectedCycleId, selectedGroupId);
    } catch (error) {
      setNotice(
        error instanceof Error
          ? error.message
          : editing
            ? "The requirement could not be updated."
            : "The requirement could not be created.",
      );
    } finally {
      setBusy(null);
    }
  };

  const activeArchiveGroup = archive || groups.find((item) => item.group_id === selectedGroupId);
  const archiveGroupName = groupDisplayLabel(
    activeArchiveGroup,
    archive?.cycle_name || selectedCycle?.display_name,
  );
  const archiveProjectName =
    archive?.project_title?.trim() || archive?.project?.title?.trim() || "";
  const archiveHeading =
    archiveProjectName && archiveProjectName !== archiveGroupName
      ? archiveProjectName
      : "Group archive";
  const archiveCycleName =
    archive?.cycle_name || selectedCycle?.display_name || "Academic cycle";
  const archiveSupervisorName = display(archive?.supervisor?.name, "Supervisor pending");

  return (
    <section
      aria-label="Document Submission Archive"
      className="admin-document-archive mx-auto w-full max-w-[1500px]"
    >
      <div className={`admin-document-archive__topbar${detailOnly ? " admin-document-archive__topbar--detail" : ""}`}>
        <div className="admin-document-archive__heading">
          <p className="admin-document-archive__eyebrow">
            {detailOnly ? "Document archive" : "Administration · Documents"}
          </p>
          <h1 className="text-3xl font-bold text-fy-text">
            {detailOnly ? archiveHeading : "Document archive"}
          </h1>
          {detailOnly ? (
            <div className="admin-document-archive__context" aria-label="Archive context">
              <span>{archiveGroupName}</span>
              <span>{archiveCycleName}</span>
              <span>{archiveSupervisorName}</span>
            </div>
          ) : (
            <p className="admin-document-archive__description">
              Review submitted requirements and open a group archive when you need the full record.
            </p>
          )}
        </div>
        {!detailOnly && <label className="grid min-w-[260px] gap-1 text-sm font-semibold text-fy-text">
          Academic cycle
          <select
            value={selectedCycleId ?? ""}
            onChange={(event) => selectCycle(event.target.value)}
            className="rounded-lg border border-fy-border bg-fy-surface px-3 py-2"
          >
            <option value="">Select a cycle</option>
            {cycles.map((cycle) => (
              <option key={cycle.id} value={cycle.id}>
                {cycle.display_name || cycle.name}
              </option>
            ))}
          </select>
        </label>}
      </div>
      {notice && (
        <p
          role="status"
          className="mt-4 rounded-lg border border-fy-border bg-fy-brand-soft px-3 py-2 text-sm text-fy-brand"
        >
          {notice}
        </p>
      )}
      {cycleState === "loading" && (
        <p className="mt-6 rounded-xl border bg-fy-surface p-5 text-sm">
          Loading academic cycles...
        </p>
      )}
      {cycleState === "error" && (
        <p
          role="alert"
          className="mt-6 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700"
        >
          Academic cycles could not be loaded.
        </p>
      )}
      {cycleState === "ready" && selectedCycleId === null && (
        <div className="mt-6 rounded-xl border border-dashed border-fy-border bg-fy-surface p-8 text-center text-sm text-fy-text-secondary">
          Select an academic cycle to view only its groups and document archive.
        </div>
      )}
      {selectedCycle && (
        <>
          {!detailOnly && <section className="admin-document-archive__management-panel mt-6 rounded-xl border border-fy-border bg-fy-surface p-5">
            <div className="admin-document-archive__section-heading">
              <div>
                <p className="admin-document-archive__eyebrow">Cycle workspace</p>
                <h2 className="text-xl font-bold text-fy-text">Requirements and groups</h2>
              </div>
              <AdminAddButton
                open={showCreate}
                label="document requirement"
                onClick={toggleCreateForm}
              />
            </div>
            {showCreate && (
                <div className="admin-document-requirement-form mt-5 grid gap-4 border-t pt-5">
                <h3 className="text-lg font-semibold">
                  {editingRequirementId === null
                    ? "Create requirement for this cycle"
                    : "Edit requirement for this cycle"}
                </h3>
                <label className="grid gap-1 text-sm">
                  Requirement name
                  <input
                    value={title}
                    onChange={(event) => setTitle(event.target.value)}
                    className="rounded border p-3"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Requirement section
                  <input
                    value={module}
                    onChange={(event) => setModule(event.target.value)}
                    className="rounded border p-3"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Instructions
                  <textarea
                    value={description}
                    onChange={(event) => setDescription(event.target.value)}
                    rows={3}
                    className="rounded border p-3"
                  />
                </label>
                <label className="grid gap-1 text-sm">
                  Deadline
                  <input
                    type="datetime-local"
                    value={deadline}
                    onChange={(event) => setDeadline(event.target.value)}
                    className="rounded border p-3"
                  />
                </label>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="grid gap-2 text-sm sm:col-span-2">
                    <span>Allowed file formats</span>
                    <div className="flex flex-wrap gap-2">
                      {fileFormatOptions.map((option) => (
                        <label
                          key={option.value}
                          className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-fy-border bg-fy-surface px-3 py-2 font-normal"
                        >
                          <input
                            type="checkbox"
                            checked={option.extensions.some((extension) =>
                              formats.includes(extension),
                            )}
                            onChange={(event) =>
                              setFormats((current) =>
                                event.target.checked
                                  ? [
                                      ...new Set([
                                        ...current.filter(
                                          (item) => !option.extensions.includes(item),
                                        ),
                                        ...option.extensions,
                                      ]),
                                    ]
                                  : current.filter(
                                      (item) => !option.extensions.includes(item),
                                    ),
                              )
                            }
                          />
                          {option.label}
                        </label>
                      ))}
                    </div>
                    <span className="text-xs font-normal text-fy-text-secondary">
                      Students may upload any file in a selected format.
                    </span>
                  </div>
                  <label className="grid gap-1 text-sm">
                    Max size (MB)
                    <input
                      type="number"
                      min="1"
                      max="100"
                      value={maxSize}
                      onChange={(event) => setMaxSize(event.target.value)}
                      className="rounded border p-3"
                    />
                  </label>
                  <label className="flex items-center gap-2 pt-6 text-sm">
                    <input
                      type="checkbox"
                      checked={required}
                      onChange={(event) => setRequired(event.target.checked)}
                    />{" "}
                    Required
                  </label>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={busy !== null}
                    onClick={() => void saveRequirement(false)}
                    className="fy-btn fy-btn--primary"
                  >
                    {editingRequirementId === null ? "Save draft" : "Save changes"}
                  </button>
                  {editingRequirementId === null && (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void saveRequirement(true)}
                      className="fy-btn fy-btn--primary"
                    >
                      Publish requirement
                    </button>
                  )}
                  {editingRequirementId !== null && (
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => {
                        setShowCreate(false);
                        resetRequirementForm();
                      }}
                      className="fy-btn"
                    >
                      Cancel
                    </button>
                  )}
                </div>
              </div>
            )}
            {!detailOnly && (
              <div className="mt-6 border-t border-fy-border pt-5">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold">Existing requirements</h3>
                  </div>
                  {requirementsState === "ready" && (
                    <span className="text-sm text-fy-text-secondary">
                      {requirements.length} requirement{requirements.length === 1 ? "" : "s"}
                    </span>
                  )}
                </div>
                {requirementsState === "loading" && (
                  <p className="mt-3 text-sm text-fy-text-secondary">
                    Loading existing requirements...
                  </p>
                )}
                {requirementsState === "error" && (
                  <p className="mt-3 text-sm text-red-700">
                    Existing requirements could not be loaded.
                  </p>
                )}
                {requirementsState === "ready" && !requirements.length && (
                  <p className="mt-3 text-sm text-fy-text-secondary">
                    No requirements have been assigned to this cycle yet.
                  </p>
                )}
                {requirementsState === "ready" && requirements.length > 0 && (
                  <div className="mt-3 grid gap-3">
                    {requirements.map((requirement) => {
                      const requirementRows = groups.flatMap((group) =>
                        (group.requirements || []).filter(
                          (row) => row.requirement_id === requirement.id,
                        ),
                      );
                      const submittedCount = requirementRows.filter(
                        (row) => !isMissingStatus(rowStatus(row)),
                      ).length;
                      const missingCount = Math.max(0, groups.length - submittedCount);
                      const selected = selectedRequirementId === requirement.id;
                      return (
                        <article
                          key={requirement.id}
                          className={`flex flex-wrap items-start justify-between gap-4 rounded-lg border p-4 transition ${selected ? "border-fy-brand bg-fy-brand-soft shadow-sm" : "border-fy-border bg-fy-surface-muted"}`}
                        >
                          <button
                            type="button"
                            aria-pressed={selected}
                            onClick={() => selectRequirement(requirement.id)}
                            className="min-w-0 flex-1 rounded-lg p-1 text-left transition hover:bg-fy-surface"
                          >
                            <div className="flex flex-wrap items-center gap-2">
                              <h4 className="font-semibold">{requirement.title}</h4>
                              <span className="rounded-full bg-fy-brand-soft px-2 py-1 text-xs font-semibold text-fy-brand">
                                {requirement.status}
                              </span>
                            </div>
                            <p className="mt-1 text-sm text-fy-text-secondary">
                              {requirement.module} · Due {dateText(requirement.due_at)} · {requirement.is_required ? "Required" : "Optional"}
                            </p>
                            <p className="mt-1 text-xs text-fy-text-secondary">
                              {groupState === "ready"
                                ? `${submittedCount} of ${groups.length} groups submitted · ${missingCount} missing`
                                : `${requirement.submission_count ?? 0} submission${requirement.submission_count === 1 ? "" : "s"}`} · Allowed: {formatLabels(requirement.allowed_file_types).join(", ") || "Custom"}
                            </p>
                            <span className="mt-3 block text-sm font-semibold text-fy-brand">
                              {selected ? "Viewing group submissions" : "View group submissions →"}
                            </span>
                          </button>
                          <button
                            type="button"
                            disabled={busy !== null || requirement.status === "ARCHIVED"}
                            onClick={() => editRequirement(requirement)}
                            className="rounded border border-fy-brand px-3 py-2 text-sm font-semibold text-fy-brand disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {requirement.status === "ARCHIVED"
                              ? "Archived (locked)"
                              : "Edit requirement"}
                          </button>
                        </article>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </section>}
          {!detailOnly && selectedRequirement && (
            <section
              className="admin-document-archive__requirement-workspace mt-6 rounded-xl border border-fy-border bg-fy-surface p-5"
              aria-labelledby="requirement-workspace-heading"
            >
              <div className="admin-document-archive__section-heading">
                <h2 id="requirement-workspace-heading" className="text-xl font-bold text-fy-text">
                  {selectedRequirement.title} · group submissions
                </h2>
                <button
                  type="button"
                  onClick={() => {
                    setSelectedRequirementId(null);
                    setRequirementStatusFilter("ALL");
                  }}
                  className="rounded border border-fy-border px-3 py-2 text-sm font-semibold text-fy-text"
                >
                  Close sheet
                </button>
              </div>
              <div className="admin-document-archive__sheet-toolbar">
                <div className="admin-document-archive__sheet-filters" role="tablist" aria-label="Filter group submissions">
                  {requirementStatusOptions.map((option) => {
                    const count = option.value === "ALL"
                      ? selectedRequirementStats.total
                      : option.value === "SUBMITTED"
                        ? selectedRequirementStats.submitted
                        : option.value === "MISSING"
                          ? selectedRequirementStats.missing
                          : option.value === "UNDER_REVIEW"
                            ? selectedRequirementStats.underReview
                            : option.value === "ACCEPTED"
                              ? selectedRequirementStats.accepted
                              : selectedRequirementStats.changesRequested;
                    const active = requirementStatusFilter === option.value;
                    return (
                      <button
                        type="button"
                        key={option.value}
                        role="tab"
                        aria-selected={active}
                        onClick={() => setRequirementStatusFilter(option.value)}
                        className={`admin-document-archive__sheet-filter${active ? " admin-document-archive__sheet-filter--active" : ""}`}
                      >
                        {option.label} <span>{count}</span>
                      </button>
                    );
                  })}
                </div>
                {requirementStatusFilter !== "ALL" && (
                  <span className="admin-document-archive__sheet-count">
                    Showing {visibleRequirementRows.length} of {selectedRequirementRows.length} groups
                  </span>
                )}
              </div>
              {!visibleRequirementRows.length ? (
                <p className="admin-document-archive__sheet-empty">
                  No groups match this status filter.
                </p>
              ) : (
                <div className="admin-document-archive__sheet-scroll">
                  <table className="admin-document-archive__sheet" aria-label={`${selectedRequirement.title} group submissions`}>
                    <thead>
                      <tr>
                        <th>Group</th>
                        <th>Project</th>
                        <th>Members</th>
                        <th>Supervisor</th>
                        <th>Status</th>
                        <th>Submission</th>
                        <th>Submitted</th>
                        <th>Review</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleRequirementRows.map(({ group, row }) => {
                        const status = rowStatus(row);
                        const fileAvailable = Boolean(row?.submission_id && row.versions.length);
                        return (
                          <tr key={`${group.group_id}-${selectedRequirement.id}`}>
                            <td data-label="Group">
                              <strong>{groupDisplayLabel(group, group.cycle_name)}</strong>
                              <small>{group.group_code}</small>
                            </td>
                            <td data-label="Project">{display(row?.project_title || group.project_title, "No project assigned")}</td>
                            <td data-label="Members">
                              <div className="admin-document-archive__sheet-members">
                                {group.members.length
                                  ? group.members.map((member) => <span key={member.id}>{member.name}</span>)
                                  : <span>No members</span>}
                              </div>
                            </td>
                            <td data-label="Supervisor">{display(group.supervisor?.name, "Not assigned")}</td>
                            <td data-label="Status"><StatusBadge status={status} /></td>
                            <td data-label="Submission">
                              <strong>{display(row?.submitted_file_name, "No file uploaded")}</strong>
                              <small>
                                {display(row?.uploader_name || row?.student_name, "No uploader recorded")}
                                {row?.registration_number ? ` · ${row.registration_number}` : ""}
                              </small>
                            </td>
                            <td data-label="Submitted">{dateText(row?.submitted_at)}</td>
                            <td data-label="Review">
                              <strong>{display(row?.reviewer_name || row?.reviewer?.name, "Not reviewed")}</strong>
                              <small>{row?.reviewer_comments || (row?.reviewed_at ? dateText(row.reviewed_at) : "Awaiting review")}</small>
                            </td>
                            <td data-label="Action">
                              <div className="admin-document-archive__sheet-actions">
                                {row?.view_url && <a href={`${api}${row.view_url}`} target="_blank" rel="noreferrer">Preview</a>}
                                {fileAvailable && row && (
                                  <button type="button" disabled={busy !== null} onClick={() => void download(row)}>
                                    Download
                                  </button>
                                )}
                                {!fileAvailable && <span>Missing</span>}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
          {!detailOnly && selectedRequirementId === null && <>
          {groupState === "loading" && (
            <p className="mt-6 rounded-xl border bg-fy-surface p-5 text-sm">
              Loading groups...
            </p>
          )}
          {groupState === "error" && (
            <p
              role="alert"
              className="mt-6 rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700"
            >
              Groups could not be loaded.
            </p>
          )}
          {groupState === "ready" && !groups.length && (
            <p className="mt-6 rounded-xl border border-dashed bg-fy-surface p-6 text-sm text-fy-text-secondary">
              This academic cycle has no groups.
            </p>
          )}
          {groupState === "ready" && groups.length > 0 && (
            <section className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5">
              <h2 className="text-lg font-semibold">Groups</h2>
              <p className="mt-1 text-sm text-fy-text-secondary">
                Group records for the selected academic cycle.
              </p>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[1100px] text-left text-sm">
                  <thead className="border-b text-xs uppercase tracking-wide text-fy-text-secondary">
                    <tr>
                      <th className="px-3 py-3">Group</th>
                      <th className="px-3 py-3">Project title</th>
                      <th className="px-3 py-3">Members</th>
                      <th className="px-3 py-3">Supervisor</th>
                      <th className="px-3 py-3">Completion</th>
                      <th className="px-3 py-3">Last submission</th>
                      <th className="px-3 py-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {groups.map((group) => (
                      <tr key={group.group_id}>
                        <td className="px-3 py-3 font-semibold">
                          {groupDisplayLabel(group, group.cycle_name)}
                        </td>
                        <td className="px-3 py-3">
                          {display(
                            group.project_title || group.project?.title,
                            "No project assigned",
                          )}
                        </td>
                        <td className="px-3 py-3">
                          {group.members.length
                            ? group.members.map((member) => (
                                <span
                                  key={member.id}
                                  className="mr-1 inline-block rounded bg-slate-100 px-2 py-1 text-xs"
                                >
                                  {member.name}
                                </span>
                              ))
                            : "No members"}
                        </td>
                        <td className="px-3 py-3">
                          {display(group.supervisor?.name)}
                        </td>
                        <td className="px-3 py-3">
                          <span className="font-semibold">
                            {group.completion_percentage}%
                          </span>
                          <span className="ml-1 text-xs text-fy-text-secondary">
                            ({group.submitted_requirement_count}/
                            {group.requirement_count})
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          {dateText(group.last_submission_at)}
                        </td>
                        <td className="px-3 py-3">
                          <button
                            type="button"
                            onClick={() => openGroup(group.group_id)}
                            className="rounded border border-fy-brand px-3 py-2 text-xs font-semibold text-fy-brand"
                          >
                            Open archive
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          </>}
          {selectedGroupId !== null && (
            <section className="admin-document-archive__detail-panel mt-6 rounded-xl border border-fy-border bg-fy-surface p-5">
              {detailState === "loading" && (
                <p className="mt-5 text-sm text-fy-text-secondary">
                  Loading group archive...
                </p>
              )}
              {detailState === "error" && (
                <p
                  role="alert"
                  className="mt-5 rounded-lg bg-red-50 p-3 text-sm text-red-700"
                >
                  The group archive could not be loaded.
                </p>
              )}
              {detailState === "ready" && archive && (
                <>
                  <div className="admin-document-archive__stats">
                    <div className="admin-document-archive__stat">
                      <span>Requirements</span>
                      <strong>{archive.filtered_requirements} / {archive.total_requirements}</strong>
                      <small>Shown in this archive</small>
                    </div>
                    <div className="admin-document-archive__stat">
                      <span>Members</span>
                      <strong>{archive.members.length}</strong>
                      <small>Active group members</small>
                    </div>
                    <div className="admin-document-archive__stat">
                      <span>Completion</span>
                      <strong>{archive.completion_percentage}%</strong>
                      <small>Requirements submitted</small>
                    </div>
                  </div>
                  <div className="admin-document-archive__requirements">
                    <div className="admin-document-archive__section-heading">
                      <div>
                        <p className="admin-document-archive__eyebrow">Archive contents</p>
                        <h2 className="text-xl font-bold text-fy-text">Submitted requirements</h2>
                      </div>
                    </div>
                    <div className="admin-document-archive__requirement-list">
                      {archive.requirements.map((row) => (
                        <article key={row.id} className="admin-document-archive__requirement-card">
                          <div className="admin-document-archive__requirement-heading">
                            <div>
                              <p className="admin-document-archive__requirement-section">
                                {row.requirement_section}
                              </p>
                              <h3>{row.requirement_name}</h3>
                              <span>{row.is_required ? "Required" : "Optional"}</span>
                            </div>
                            <StatusBadge status={row.current_status} />
                          </div>
                          <div className="admin-document-archive__requirement-meta">
                            <div><span>File</span><strong>{display(row.submitted_file_name, "No file uploaded")}</strong></div>
                            <div><span>Submitted</span><strong>{dateText(row.submitted_at)}</strong></div>
                            <div><span>Uploader</span><strong>{display(row.uploader_name, "Not recorded")}</strong></div>
                            <div><span>Registration</span><strong>{display(row.registration_number, "Not recorded")}</strong></div>
                            <div><span>Version</span><strong>{row.version_number ? `v${row.version_number}` : "Not recorded"}</strong></div>
                            <div><span>Reviewer</span><strong>{display(row.reviewer_name || row.reviewer?.name, "Not reviewed")}</strong></div>
                            <div><span>Review date</span><strong>{row.reviewed_at ? dateText(row.reviewed_at) : "Not reviewed"}</strong></div>
                          </div>
                          {row.reviewer_comments && (
                            <div className="admin-document-archive__comment">
                              <span>Reviewer comment</span>
                              <p>{row.reviewer_comments}</p>
                            </div>
                          )}
                          <div className="admin-document-archive__requirement-actions">
                            {row.submission_id && row.versions.length > 0 ? (
                              <button
                                type="button"
                                disabled={busy !== null}
                                onClick={() => void download(row)}
                                className="fy-btn fy-btn--secondary fy-btn--sm"
                              >
                                Download file
                              </button>
                            ) : (
                              <span>No file available</span>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  </div>
                </>
              )}
            </section>
          )}
        </>
      )}
    </section>
  );
}
