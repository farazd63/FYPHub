import { useCallback, useEffect, useMemo, useState } from "react";
import { BackButton, StatusBadge } from "./ui";
import { AdminAddButton } from "./ui/AdminAddButton";
import { appPathname } from "./platform-path";
import "./admin-document-archive.css";

type Cycle = {
  id: number;
  code: string;
  name: string;
  display_name: string;
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
  group_name?: string | null;
  project_title?: string | null;
  project?: {
    id: number;
    title?: string | null;
    status?: string | null;
  } | null;
  members: Member[];
  supervisor: Person;
  completion_percentage: number;
  last_submission_at?: string | null;
  requirement_count: number;
  submitted_requirement_count: number;
  status: string;
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
      setCycles(Array.isArray(body) ? (body as Cycle[]) : []);
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
          body &&
            typeof body === "object" &&
            Array.isArray((body as { groups?: unknown }).groups)
            ? (body as { groups: Group[] }).groups
            : [],
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
        setArchive(null);
        setGroupState("idle");
        setDetailState("idle");
        return;
      }
      setSelectedGroupId(null);
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
    setArchive(null);
    setSelectedCycleId(value ? Number(value) : null);
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

  return (
    <section
      aria-label="Document Submission Archive"
      className="mx-auto w-full max-w-[1500px]"
    >
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          {detailOnly && (
            <BackButton
              onClick={() => window.location.assign("/admin/document-requirements")}
            >
              Back to archive
            </BackButton>
          )}
          <h1 className="text-3xl font-bold text-fy-text">
            {detailOnly ? "Group document archive" : "Document Submission Archive"}
          </h1>
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
                {cycle.display_name || cycle.name} ({cycle.code})
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
          {!detailOnly && <section className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                  Selected cycle
                </p>
                <h2 className="text-xl font-bold text-fy-text">
                  {selectedCycle.display_name || selectedCycle.name}
                </h2>
                <p className="text-sm text-fy-text-secondary">
                  {selectedCycle.code}
                </p>
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
                    <p className="text-sm text-fy-text-secondary">
                      Requirements already assigned to this academic cycle can be edited here.
                    </p>
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
                    {requirements.map((requirement) => (
                      <article
                        key={requirement.id}
                        className="flex flex-wrap items-start justify-between gap-4 rounded-lg border border-fy-border bg-fy-surface-muted p-4"
                      >
                        <div className="min-w-0">
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
                            {requirement.submission_count ?? 0} submission{requirement.submission_count === 1 ? "" : "s"} · Allowed: {formatLabels(requirement.allowed_file_types).join(", ") || "Custom"}
                          </p>
                        </div>
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
                    ))}
                  </div>
                )}
              </div>
            )}
          </section>}
          {!detailOnly && <>
          {groupState === "loading" && (
            <p className="mt-6 rounded-xl border bg-fy-surface p-5 text-sm">
              Loading groups for{" "}
              {selectedCycle.display_name || selectedCycle.name}...
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
              <h2 className="text-lg font-semibold">
                Groups in {selectedCycle.display_name || selectedCycle.name}
              </h2>
              <div className="mt-4 overflow-x-auto">
                <table className="w-full min-w-[1100px] text-left text-sm">
                  <thead className="border-b text-xs uppercase tracking-wide text-fy-text-secondary">
                    <tr>
                      <th className="px-3 py-3">Group code</th>
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
                          {group.group_code}
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
            <section className="mt-6 rounded-xl border border-fy-border bg-fy-surface p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wide text-fy-text-secondary">
                    Group archive
                  </p>
                  <h2 className="text-xl font-bold text-fy-text">
                    {archive?.group_code ||
                      groups.find((item) => item.group_id === selectedGroupId)
                        ?.group_code}
                  </h2>
                  <p className="text-sm text-fy-text-secondary">
                    {display(
                      archive?.project_title || archive?.project?.title,
                      "No project assigned",
                    )}{" "}
                    ·{" "}
                    {display(
                      archive?.supervisor?.name,
                      "No supervisor assigned",
                    )}
                  </p>
                </div>
                <BackButton
                  onClick={() => {
                    if (detailOnly) {
                      window.location.assign("/admin/document-requirements");
                    } else {
                      setSelectedGroupId(null);
                      setArchive(null);
                    }
                  }}
                >
                  {detailOnly ? "Back to archive" : "Back to groups"}
                </BackButton>
              </div>
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
                  <div className="mt-5 grid gap-3 sm:grid-cols-4">
                    <div className="rounded-lg bg-fy-surface-muted p-3">
                      <span className="block text-xs uppercase text-fy-text-secondary">
                        Cycle
                      </span>
                      <strong>{archive.cycle_name}</strong>
                    </div>
                    <div className="rounded-lg bg-fy-surface-muted p-3">
                      <span className="block text-xs uppercase text-fy-text-secondary">
                        Project
                      </span>
                      <strong>
                        {display(
                          archive.project_title || archive.project?.title,
                          "No project assigned",
                        )}
                      </strong>
                    </div>
                    <div className="rounded-lg bg-fy-surface-muted p-3">
                      <span className="block text-xs uppercase text-fy-text-secondary">
                        Members
                      </span>
                      <strong>{archive.members.length}</strong>
                    </div>
                    <div className="rounded-lg bg-fy-surface-muted p-3">
                      <span className="block text-xs uppercase text-fy-text-secondary">
                        Completion
                      </span>
                      <strong>{archive.completion_percentage}%</strong>
                    </div>
                  </div>
                  <p className="mt-4 text-sm text-fy-text-secondary">
                    Showing {archive.filtered_requirements} of{" "}
                    {archive.total_requirements} requirements.
                  </p>
                  <div className="admin-document-archive__records mt-3">
                    <table className="admin-document-archive__table w-full text-left text-xs">
                      <thead className="border-b bg-fy-surface-muted uppercase tracking-wide text-fy-text-secondary">
                        <tr>
                          <th className="px-2 py-3">Cycle</th>
                          <th className="px-2 py-3">Group</th>
                          <th className="px-2 py-3">Section</th>
                          <th className="px-2 py-3">Requirement</th>
                          <th className="px-2 py-3">Group / uploader</th>
                          <th className="px-2 py-3">Registration</th>
                          <th className="px-2 py-3">File</th>
                          <th className="px-2 py-3">Submitted</th>
                          <th className="px-2 py-3">Version</th>
                          <th className="px-2 py-3">Status</th>
                          <th className="px-2 py-3">Reviewer</th>
                          <th className="px-2 py-3">Review date</th>
                          <th className="px-2 py-3">Comments</th>
                          <th className="px-2 py-3">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="admin-document-archive__body">
                        {archive.requirements.map((row) => (
                          <tr key={row.id} className="align-top">
                            <td data-label="Cycle" className="px-2 py-3">{row.cycle_name}</td>
                            <td data-label="Group" className="px-2 py-3 font-semibold">
                              {row.group_code}
                            </td>
                            <td data-label="Section" className="px-2 py-3">
                              {row.requirement_section}
                            </td>
                            <td data-label="Requirement" className="px-2 py-3">
                              <strong>{row.requirement_name}</strong>
                              <span className="block text-fy-text-secondary">
                                {row.is_required ? "Required" : "Optional"}
                              </span>
                            </td>
                            <td data-label="Group / uploader" className="px-2 py-3">
                              <strong>
                                {display(row.group_name, row.group_code)}
                              </strong>
                              <span className="block text-fy-text-secondary">
                                Uploaded by: {display(row.uploader_name, "-")}
                              </span>
                            </td>
                            <td data-label="Registration" className="px-2 py-3">
                              {display(row.registration_number, "-")}
                            </td>
                            <td data-label="File" className="px-2 py-3">
                              {display(row.submitted_file_name, "No file")}
                            </td>
                            <td data-label="Submitted" className="px-2 py-3">
                              {dateText(row.submitted_at)}
                            </td>
                            <td data-label="Version" className="px-2 py-3">
                              {row.version_number
                                ? `v${row.version_number}`
                                : "-"}
                            </td>
                            <td data-label="Status" className="px-2 py-3">
                              <StatusBadge status={row.current_status} />
                            </td>
                            <td data-label="Reviewer" className="px-2 py-3">
                              {display(
                                row.reviewer_name || row.reviewer?.name,
                                "-",
                              )}
                            </td>
                            <td data-label="Review date" className="px-2 py-3">
                              {row.reviewed_at
                                ? dateText(row.reviewed_at)
                                : "-"}
                            </td>
                            <td data-label="Comments" className="max-w-[220px] whitespace-pre-wrap px-2 py-3">
                              {display(row.reviewer_comments, "-")}
                            </td>
                            <td data-label="Actions" className="px-2 py-3">
                              <div className="flex min-w-[230px] flex-wrap gap-1">
                                {row.submission_id &&
                                  row.versions.length > 0 && (
                                    <button
                                      type="button"
                                      disabled={busy !== null}
                                      onClick={() => void download(row)}
                                      className="rounded border border-fy-brand px-2 py-1 font-semibold text-fy-brand"
                                    >
                                      Download
                                    </button>
                                  )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
              {archive &&
                archive.requirements.some(
                  (row) => row.review_history.length > 0,
                ) && (
                  <section className="mt-6 rounded-lg border bg-fy-surface-muted p-4">
                    <h3 className="font-semibold">Review history</h3>
                    <div className="mt-3 grid gap-3">
                      {archive.requirements.map((row) =>
                        row.review_history.length ? (
                          <article
                            key={`history-${row.id}`}
                            className="rounded border bg-fy-surface p-3 text-sm"
                          >
                            <strong>{row.requirement_name}</strong>
                            <div className="mt-2 grid gap-2">
                              {row.review_history.map((event) => (
                                <div key={event.id}>
                                  <StatusBadge status={event.status} /> ·{" "}
                                  {display(event.reviewer?.name, "Reviewer")} ·{" "}
                                  {event.reviewed_at
                                    ? dateText(event.reviewed_at)
                                    : "No date"}
                                  {event.comment && (
                                    <p className="text-fy-text-secondary">
                                      {event.comment}
                                    </p>
                                  )}
                                </div>
                              ))}
                            </div>
                          </article>
                        ) : null,
                      )}
                    </div>
                  </section>
                )}
            </section>
          )}
        </>
      )}
    </section>
  );
}
