import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from "react";
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Circle,
  Download,
  Edit3,
  Eraser,
  FileText,
  Highlighter,
  MessageCircle,
  MessageSquare,
  MousePointer2,
  Redo2,
  Save,
  Search,
  Send,
  Square,
  StickyNote,
  Strikethrough,
  TextCursorInput,
  Underline,
  Undo2,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Document as PdfDocument, Page, pdfjs } from "react-pdf";
import { ModalPortal } from "../../ui/ModalPortal";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "./interactive-proposal-review.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

type ReviewRole = "supervisor" | "student";
type ReviewTool =
  | "SELECT"
  | "HIGHLIGHT"
  | "UNDERLINE"
  | "STRIKETHROUGH"
  | "PEN"
  | "RECTANGLE"
  | "CIRCLE"
  | "ARROW"
  | "TEXT_BOX"
  | "STICKY_NOTE"
  | "ERASER";
type PersistedAnnotationType = Exclude<ReviewTool, "SELECT" | "ERASER">;
type FeedbackType = "GENERAL_COMMENT" | "CORRECTION" | "EDITING_SUGGESTION" | "FORMAL_REVISION_REQUEST";
type CorrectionAction = "NONE" | "REMOVE" | "REPLACE" | "ADD" | "MOVE" | "REWRITE" | "EXPAND" | "CORRECT" | "FORMATTING";
type TargetScope = "PARAGRAPH" | "SECTION" | "MODULE" | "FULL_PROPOSAL";
type Priority = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
type Rect = { x: number; y: number; width: number; height: number };
type Point = { x: number; y: number };
type Geometry = { rects?: Rect[]; x?: number; y?: number; width?: number; height?: number; start?: Point; end?: Point };
type Drawing = { points?: Point[] };
type SelectionContext = { page: number; text: string; rects: Rect[]; left: number; top: number; annotationId: number | null };

type Annotation = {
  id: number;
  submission_id: number;
  version_id?: number;
  author_name: string;
  annotation_type: ReviewTool;
  page_number: number;
  geometry: Geometry;
  drawing: Drawing;
  selected_text: string | null;
  content: string | null;
  suggested_text: string | null;
  color: string;
  stroke_width: number;
  publication_status: "DRAFT" | "PUBLISHED" | "WITHDRAWN";
  feedback_id: number | null;
  revision_request_id: number | null;
  created_at: string;
};

export type DocumentReviewContext = {
  requirementId: number;
  submissionId: number;
  versionId: number;
  title: string;
  filename: string;
  version: number;
  mimeType?: string;
  previewUrl: string;
  downloadUrl?: string | null;
  status?: string;
};

type FeedbackMessage = { id: number; sender_id: number; sender_name: string; body: string; created_at: string };
type Feedback = {
  id: number;
  marker_number?: number;
  submission_id: number;
  author: { id: number; name: string };
  feedback_level: TargetScope;
  feedback_type: FeedbackType | "FORMAL_REVISION" | "CLARIFICATION_REQUEST";
  correction_action: CorrectionAction;
  title: string;
  content: string;
  suggested_text: string | null;
  selected_text: string | null;
  location: Record<string, unknown>;
  destination_location: Record<string, unknown>;
  expected_outcome: string | null;
  is_mandatory: boolean;
  priority: Priority;
  due_at: string | null;
  workflow_status: "OPEN" | "ADDRESSED" | "VERIFIED";
  publication_status: "DRAFT" | "PUBLISHED" | "WITHDRAWN";
  created_at: string;
  updated_at?: string;
  messages: FeedbackMessage[];
};

type FeedbackDraft = {
  feedback_type: FeedbackType;
  correction_action: CorrectionAction;
  target_scope: TargetScope;
  title: string;
  content: string;
  suggested_text: string;
  destination: string;
  expected_outcome: string;
  selected_text: string;
  location: Record<string, unknown>;
  is_mandatory: boolean;
  priority: Priority;
  due_at: string;
};

type PointDrawing = { page: number; start: Point; points: Point[] };
type ContextAction = "HIGHLIGHT" | "UNDERLINE" | "STRIKETHROUGH" | "ADD_COMMENT" | "SUGGEST_REPLACEMENT" | "REQUEST_CORRECTION";

const reviewTools: Array<{ id: ReviewTool; label: string; icon: typeof MousePointer2 }> = [
  { id: "SELECT", label: "Select", icon: MousePointer2 },
  { id: "HIGHLIGHT", label: "Highlight", icon: Highlighter },
  { id: "UNDERLINE", label: "Underline", icon: Underline },
  { id: "STRIKETHROUGH", label: "Strikethrough", icon: Strikethrough },
  { id: "PEN", label: "Pen", icon: Edit3 },
  { id: "RECTANGLE", label: "Rectangle", icon: Square },
  { id: "CIRCLE", label: "Circle", icon: Circle },
  { id: "ARROW", label: "Arrow", icon: ArrowUpRight },
  { id: "TEXT_BOX", label: "Text box", icon: TextCursorInput },
  { id: "STICKY_NOTE", label: "Sticky note", icon: StickyNote },
  { id: "ERASER", label: "Eraser", icon: Eraser },
];

const textSelectionTools: ReviewTool[] = ["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH"];
const persistedAnnotationTypes = new Set<PersistedAnnotationType>([
  "HIGHLIGHT",
  "UNDERLINE",
  "STRIKETHROUGH",
  "PEN",
  "RECTANGLE",
  "CIRCLE",
  "ARROW",
  "TEXT_BOX",
  "STICKY_NOTE",
]);
const feedbackTypes: Array<{ value: FeedbackType | "ALL"; label: string }> = [
  { value: "ALL", label: "All types" },
  { value: "GENERAL_COMMENT", label: "General comments" },
  { value: "CORRECTION", label: "Corrections" },
  { value: "EDITING_SUGGESTION", label: "Editing suggestions" },
  { value: "FORMAL_REVISION_REQUEST", label: "Formal revision requests" },
];

const emptyDraft = (page = 1): FeedbackDraft => ({
  feedback_type: "GENERAL_COMMENT",
  correction_action: "NONE",
  target_scope: "PARAGRAPH",
  title: "",
  content: "",
  suggested_text: "",
  destination: "",
  expected_outcome: "",
  selected_text: "",
  location: { page_number: page },
  is_mandatory: false,
  priority: "MEDIUM",
  due_at: "",
});

function clamp(value: number) {
  return Math.max(0, Math.min(1, value));
}

function apiError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      const structured = detail as { message: unknown; fields?: unknown };
      const fields = Array.isArray(structured.fields)
        ? structured.fields
            .filter((field): field is { path?: unknown; code?: unknown } => Boolean(field && typeof field === "object"))
            .map((field) => `${String(field.path || "request")} (${String(field.code || "invalid")})`)
            .join(", ")
        : "";
      return fields ? `${String(structured.message)}: ${fields}` : String(structured.message);
    }
  }
  return fallback;
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: "include", ...init });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(apiError(body, "Request failed (" + response.status + ")."));
  return body as T;
}

function rectFromClient(rect: DOMRect, page: DOMRect): Rect {
  return {
    x: clamp((rect.left - page.left) / page.width),
    y: clamp((rect.top - page.top) / page.height),
    width: clamp(rect.width / page.width),
    height: clamp(rect.height / page.height),
  };
}

function markerNumber(row: Feedback) {
  return row.marker_number ?? row.id;
}

function feedbackTypeLabel(value: string) {
  return value
    .replace("FORMAL_REVISION_REQUEST", "FORMAL REVISION REQUEST")
    .replace("EDITING_SUGGESTION", "EDITING SUGGESTION")
    .replace("GENERAL_COMMENT", "GENERAL COMMENT")
    .replaceAll("_", " ");
}

function scopeLabel(value: string) {
  return value.replaceAll("_", " ").toLowerCase().replace(/^\w/, (match) => match.toUpperCase());
}

function priorityLabel(value: Priority) {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return "";
  return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function localDateTimeValue(value: string | null | undefined) {
  if (!value) return "";
  const date = new Date(value);
  const pad = (part: number) => String(part).padStart(2, "0");
  return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate()) + "T" + pad(date.getHours()) + ":" + pad(date.getMinutes());
}

function defaultColorForTool(tool: ReviewTool) {
  if (tool === "HIGHLIGHT") return "#FACC15";
  if (["PEN", "UNDERLINE", "STRIKETHROUGH", "RECTANGLE", "CIRCLE", "ARROW", "TEXT_BOX"].includes(tool)) return "#DC2626";
  return "#2563EB";
}

function feedbackColor(type: FeedbackType) {
  if (type === "FORMAL_REVISION_REQUEST") return "#7C3AED";
  return "#2563EB";
}

function annotationColorForFeedback(annotationType: ReviewTool, type: FeedbackType) {
  if (annotationType === "HIGHLIGHT") return "#FACC15";
  if (["PEN", "UNDERLINE", "STRIKETHROUGH", "RECTANGLE", "CIRCLE", "ARROW"].includes(annotationType)) return "#DC2626";
  return feedbackColor(type);
}

function isEmptyTextAnnotation(row: Annotation) {
  return (row.annotation_type === "STICKY_NOTE" || row.annotation_type === "TEXT_BOX") && !row.content?.trim() && !row.feedback_id;
}

function isPersistableAnnotation(row: Annotation) {
  return persistedAnnotationTypes.has(row.annotation_type as PersistedAnnotationType) && !isEmptyTextAnnotation(row);
}

function annotationLocation(row: Annotation) {
  return { page_number: row.page_number, ...row.geometry };
}

function geometryPayload(annotation: Annotation, publicationStatus = annotation.publication_status) {
  return {
    submission_id: annotation.submission_id,
    version_id: annotation.version_id,
    annotation_type: annotation.annotation_type,
    page_number: annotation.page_number,
    geometry: annotation.geometry,
    drawing: annotation.drawing,
    selected_text: annotation.selected_text,
    content: annotation.content,
    suggested_text: annotation.suggested_text,
    color: annotation.color,
    stroke_width: annotation.stroke_width,
    publication_status: publicationStatus,
    feedback_id: annotation.feedback_id,
    revision_request_id: annotation.revision_request_id,
  };
}

export function InteractiveProposalReview({
  api,
  submissionId,
  title,
  version,
  role,
  onClose,
  documentContext,
  onDecision,
}: {
  api: string;
  submissionId: number;
  title: string;
  version: number;
  role: ReviewRole;
  onClose: () => void;
  documentContext?: DocumentReviewContext;
  onDecision?: (decision: "approve" | "request-replacement" | "reject", comment: string) => Promise<void>;
}) {
  const [fileUrl, setFileUrl] = useState("");
  const [pageCount, setPageCount] = useState(0);
  const [activePage, setActivePage] = useState(1);
  const [pageWidth, setPageWidth] = useState(760);
  const [zoom, setZoom] = useState(1);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [feedback, setFeedback] = useState<Feedback[]>([]);
  const [selectedAnnotationId, setSelectedAnnotationId] = useState<number | null>(null);
  const [selectedFeedbackId, setSelectedFeedbackId] = useState<number | null>(null);
  const [tool, setTool] = useState<ReviewTool>("SELECT");
  const [color, setColor] = useState(defaultColorForTool("SELECT"));
  const [strokeWidth, setStrokeWidth] = useState(3);
  const [search, setSearch] = useState("");
  const [showFeedbackForm, setShowFeedbackForm] = useState(false);
  const [editingFeedbackId, setEditingFeedbackId] = useState<number | null>(null);
  const [feedbackDraft, setFeedbackDraft] = useState<FeedbackDraft>(() => emptyDraft());
  const [threadDraft, setThreadDraft] = useState("");
  const [annotationNote, setAnnotationNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [closePrompt, setClosePrompt] = useState(false);
  const [undo, setUndo] = useState<Annotation[][]>([]);
  const [redo, setRedo] = useState<Annotation[][]>([]);
  const [drawing, setDrawing] = useState<PointDrawing | null>(null);
  const [contextualSelection, setContextualSelection] = useState<SelectionContext | null>(null);
  const [decisionComment, setDecisionComment] = useState("");
  const [feedbackTypeFilter, setFeedbackTypeFilter] = useState<FeedbackType | "ALL">("ALL");
  const [pageFilter, setPageFilter] = useState<"ALL" | number>("ALL");
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const feedbackCardRefs = useRef<Record<number, HTMLElement | null>>({});
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const fileUrlRef = useRef("");
  const localId = useRef(-1);

  const reviewRoot = documentContext ? api + "/api/v1/document-review" : api + "/api/v1/supervisor-review";
  const annotationCollection = documentContext
    ? reviewRoot + "/submissions/" + submissionId + "/annotations?version_id=" + documentContext.versionId
    : reviewRoot + "/proposals/" + submissionId + "/annotations";
  const feedbackCollection = documentContext
    ? reviewRoot + "/submissions/" + submissionId + "/feedback?version_id=" + documentContext.versionId
    : reviewRoot + "/proposals/" + submissionId + "/feedback";

  const canEdit = role === "supervisor";
  const selectedAnnotation = useMemo(() => annotations.find((item) => item.id === selectedAnnotationId) ?? null, [annotations, selectedAnnotationId]);
  const selectedFeedback = useMemo(() => feedback.find((item) => item.id === selectedFeedbackId) ?? null, [feedback, selectedFeedbackId]);
  const feedbackById = useMemo(() => new Map(feedback.map((item) => [item.id, item])), [feedback]);
  const visibleAnnotations = useMemo(
    () => annotations.filter((item) => item.publication_status !== "WITHDRAWN" && isPersistableAnnotation(item)),
    [annotations],
  );
  const pageAnnotations = useCallback((page: number) => visibleAnnotations.filter((item) => item.page_number === page), [visibleAnnotations]);
  const filteredFeedback = useMemo(
    () =>
      feedback
        .filter((row) => feedbackTypeFilter === "ALL" || row.feedback_type === feedbackTypeFilter || (feedbackTypeFilter === "FORMAL_REVISION_REQUEST" && row.feedback_type === "FORMAL_REVISION"))
        .filter((row) => pageFilter === "ALL" || Number(row.location?.page_number) === pageFilter)
        .sort((left, right) => markerNumber(left) - markerNumber(right)),
    [feedback, feedbackTypeFilter, pageFilter],
  );
  const overlayInteractive = canEdit && !textSelectionTools.includes(tool) && tool !== "SELECT" && tool !== "ERASER";

  useEffect(() => {
    document.body.classList.add("fy-modal-open");
    return () => document.body.classList.remove("fy-modal-open");
  }, []);

  const load = useCallback(async () => {
    setError("");
    try {
      const [documentResponse, rows, feedbackRows] = await Promise.all([
        fetch(documentContext ? api + documentContext.previewUrl : api + "/api/v1/proposal-compliance/reports/" + submissionId + "/original", { credentials: "include" }),
        requestJson<Annotation[]>(annotationCollection),
        requestJson<Feedback[]>(feedbackCollection),
      ]);
      if (!documentResponse.ok) throw new Error((await documentResponse.text()) || "The proposal document could not be opened.");
      const blobUrl = URL.createObjectURL(await documentResponse.blob());
      setFileUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        fileUrlRef.current = blobUrl;
        return blobUrl;
      });
      setAnnotations(rows);
      setFeedback(feedbackRows);
      setDirty(false);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The review workspace could not be loaded.");
    }
  }, [api, annotationCollection, documentContext, feedbackCollection, submissionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => {
      window.clearTimeout(timer);
      if (fileUrlRef.current) URL.revokeObjectURL(fileUrlRef.current);
    };
  }, [load]);

  useEffect(() => {
    const measure = () => {
      const available = (scrollRef.current?.clientWidth ?? window.innerWidth * 0.58) - 36;
      setPageWidth(Math.max(420, Math.min(980, available)));
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (scrollRef.current) observer.observe(scrollRef.current);
    window.addEventListener("resize", measure);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);

  const saveAll = useCallback(
    async (publish: boolean): Promise<boolean> => {
      if (!canEdit) return true;
      setSaving(true);
      setError("");
      setMessage("");
      try {
        let nextAnnotations = [...annotations];
        for (const row of nextAnnotations.filter((item) => item.publication_status !== "WITHDRAWN" && isPersistableAnnotation(item))) {
          if (row.id < 0) {
            const saved = await requestJson<Annotation>(annotationCollection.split("?")[0], {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(geometryPayload(row, publish ? "PUBLISHED" : "DRAFT")),
            });
            nextAnnotations = nextAnnotations.map((item) => (item.id === row.id ? saved : item));
          } else if (publish && row.publication_status === "DRAFT") {
            const saved = await requestJson<Annotation>(reviewRoot + "/annotations/" + row.id + "/publish", { method: "POST" });
            nextAnnotations = nextAnnotations.map((item) => (item.id === row.id ? saved : item));
          }
        }
        for (const row of annotations.filter((item) => item.id > 0 && (item.publication_status === "WITHDRAWN" || !isPersistableAnnotation(item)))) {
          await requestJson(reviewRoot + "/annotations/" + row.id + "/withdraw", { method: "POST" });
        }
        let nextFeedback = [...feedback];
        if (publish) {
          for (const row of nextFeedback.filter((item) => item.publication_status === "DRAFT")) {
            const saved = await requestJson<Feedback>(reviewRoot + "/feedback/" + row.id + "/publish", { method: "POST" });
            nextFeedback = nextFeedback.map((item) => (item.id === row.id ? saved : item));
          }
        }
        setAnnotations(nextAnnotations);
        setFeedback(nextFeedback);
        setDirty(false);
        setMessage(publish ? "Feedback published. Students have been notified." : "All review changes are saved as a draft.");
        return true;
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "The review could not be saved.");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [annotationCollection, annotations, canEdit, feedback, reviewRoot, submissionId],
  );

  useEffect(() => {
    if (!canEdit || !dirty || saving || showFeedbackForm) return;
    const timer = window.setTimeout(() => void saveAll(false), 1500);
    return () => window.clearTimeout(timer);
  }, [canEdit, dirty, saveAll, saving, showFeedbackForm]);

  const commit = (next: Annotation[]) => {
    setUndo((current) => [...current, annotations].slice(-30));
    setRedo([]);
    setAnnotations(next);
    setDirty(true);
  };

  const scrollToPage = (page: number) => {
    const nextPage = Math.max(1, Math.min(pageCount || page, page));
    setActivePage(nextPage);
    pageRefs.current[nextPage]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const scrollToAnnotation = (row: Annotation) => {
    scrollToPage(row.page_number);
    window.requestAnimationFrame(() => {
      const container = scrollRef.current;
      const page = pageRefs.current[row.page_number];
      if (!container || !page) return;
      const firstRect = row.geometry.rects?.[0];
      const y = firstRect ? firstRect.y * page.getBoundingClientRect().height : (row.geometry.y ?? 0) * page.getBoundingClientRect().height;
      container.scrollTo({ top: Math.max(0, page.offsetTop + y - 76), behavior: "smooth" });
    });
  };

  const scrollFeedbackCard = (feedbackId: number) => {
    setFeedbackTypeFilter("ALL");
    setPageFilter("ALL");
    window.requestAnimationFrame(() => feedbackCardRefs.current[feedbackId]?.scrollIntoView({ behavior: "smooth", block: "nearest" }));
  };

  const pointFromEvent = (event: ReactPointerEvent, page: number): Point => {
    const rect = pageRefs.current[page]?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: clamp((event.clientX - rect.left) / rect.width), y: clamp((event.clientY - rect.top) / rect.height) };
  };

  const selectionGeometry = (page: number): { rects: Rect[]; text: string; left: number; top: number } | null => {
    const selection = window.getSelection();
    const container = pageRefs.current[page];
    if (!selection || selection.isCollapsed || !selection.rangeCount || !container) return null;
    const pageRect = container.getBoundingClientRect();
    const range = selection.getRangeAt(0);
    const rects = Array.from(range.getClientRects())
      .map((rect) => rectFromClient(rect, pageRect))
      .filter((rect) => rect.width > 0.002 && rect.height > 0.002);
    const text = selection.toString().trim();
    const screenRect = range.getBoundingClientRect();
    if (!rects.length || !text) return null;
    return { rects, text, left: clamp((screenRect.left - pageRect.left) / pageRect.width), top: clamp((screenRect.top - pageRect.top) / pageRect.height) };
  };

  const addAnnotation = (
    page: number,
    annotationType: PersistedAnnotationType,
    geometry: Geometry,
    selectedText: string | null,
    drawingData: Drawing = {},
    annotationColor = color,
  ): Annotation => {
    const row: Annotation = {
      id: localId.current--,
      submission_id: submissionId,
      version_id: documentContext?.versionId,
      author_name: "You",
      annotation_type: annotationType,
      page_number: page,
      geometry,
      drawing: drawingData,
      selected_text: selectedText,
      content: null,
      suggested_text: null,
      color: annotationColor,
      stroke_width: strokeWidth,
      publication_status: "DRAFT",
      feedback_id: null,
      revision_request_id: null,
      created_at: new Date().toISOString(),
    };
    commit([...annotations, row]);
    setSelectedAnnotationId(row.id);
    setAnnotationNote("");
    return row;
  };

  const openFeedbackFor = (annotation: Annotation | null = null, preset: Partial<FeedbackDraft> = {}) => {
    const page = annotation?.page_number ?? activePage;
    const base = emptyDraft(page);
    setSelectedAnnotationId(annotation?.id ?? selectedAnnotationId);
    if (annotation) {
      setAnnotationNote(annotation.content ?? "");
      setFeedbackDraft({
        ...base,
        selected_text: annotation.selected_text ?? "",
        location: annotationLocation(annotation),
        content: annotation.content ?? "",
        ...preset,
      });
      scrollToAnnotation(annotation);
    } else {
      setFeedbackDraft({ ...base, ...preset, location: { page_number: page, ...(preset.location ?? {}) } });
    }
    setEditingFeedbackId(null);
    setShowFeedbackForm(true);
    setContextualSelection(null);
  };

  const feedbackDraftFromRow = (row: Feedback): FeedbackDraft => ({
    feedback_type: row.feedback_type === "FORMAL_REVISION" ? "FORMAL_REVISION_REQUEST" : (row.feedback_type as FeedbackType),
    correction_action: row.correction_action,
    target_scope: row.feedback_level,
    title: row.title,
    content: row.content,
    suggested_text: row.suggested_text ?? "",
    destination: typeof row.destination_location?.description === "string" ? row.destination_location.description : "",
    expected_outcome: row.expected_outcome ?? "",
    selected_text: row.selected_text ?? "",
    location: row.location ?? {},
    is_mandatory: row.is_mandatory,
    priority: row.priority ?? "MEDIUM",
    due_at: localDateTimeValue(row.due_at),
  });

  const editFeedback = (row: Feedback) => {
    const linked = annotations.find((annotation) => annotation.feedback_id === row.id && annotation.publication_status !== "WITHDRAWN") ?? null;
    setSelectedFeedbackId(row.id);
    if (linked) {
      setSelectedAnnotationId(linked.id);
      setAnnotationNote(linked.content ?? "");
      scrollToAnnotation(linked);
    } else {
      scrollToPage(Number(row.location?.page_number) || 1);
    }
    setFeedbackDraft(feedbackDraftFromRow(row));
    setEditingFeedbackId(row.id);
    setShowFeedbackForm(true);
    setError("");
  };

  const handleTextSelection = (page: number) => {
    if (!canEdit) return;
    const selection = selectionGeometry(page);
    if (!selection) return;
    let annotationId: number | null = null;
    if (textSelectionTools.includes(tool)) {
      const annotationType = tool as PersistedAnnotationType;
      const row = addAnnotation(page, annotationType, { rects: selection.rects }, selection.text, {}, defaultColorForTool(annotationType));
      annotationId = row.id;
    }
    setFeedbackDraft((current) => ({ ...current, selected_text: selection.text, location: { page_number: page, rects: selection.rects } }));
    setContextualSelection({ page, text: selection.text, rects: selection.rects, left: selection.left, top: selection.top, annotationId });
    window.getSelection()?.removeAllRanges();
  };

  const ensureSelectionAnnotation = (annotationType: PersistedAnnotationType, annotationColor: string) => {
    if (!contextualSelection) return null;
    if (contextualSelection.annotationId !== null) {
      const existing = annotations.find((row) => row.id === contextualSelection.annotationId) ?? null;
      if (existing) return existing;
    }
    const first = contextualSelection.rects[0];
    return addAnnotation(
      contextualSelection.page,
      annotationType,
      annotationType === "STICKY_NOTE"
        ? { x: first.x, y: first.y, width: Math.max(first.width, 0.028), height: Math.max(first.height, 0.028) }
        : { rects: contextualSelection.rects },
      contextualSelection.text,
      {},
      annotationColor,
    );
  };

  const handleContextualAction = (action: ContextAction) => {
    if (!contextualSelection) return;
    if (action === "HIGHLIGHT" || action === "UNDERLINE" || action === "STRIKETHROUGH") {
      setTool(action);
      const existing = contextualSelection.annotationId === null ? null : annotations.find((row) => row.id === contextualSelection.annotationId);
      const row = existing?.annotation_type === action ? existing : ensureSelectionAnnotation(action, defaultColorForTool(action));
      if (row) {
        setSelectedAnnotationId(row.id);
        setContextualSelection({ ...contextualSelection, annotationId: row.id });
      }
      return;
    }
    const row = ensureSelectionAnnotation("STICKY_NOTE", action === "REQUEST_CORRECTION" ? "#7C3AED" : "#2563EB");
    if (!row) return;
    const preset: Partial<FeedbackDraft> =
      action === "SUGGEST_REPLACEMENT"
        ? { feedback_type: "EDITING_SUGGESTION", correction_action: "REPLACE", title: "Suggested replacement" }
        : action === "REQUEST_CORRECTION"
          ? { feedback_type: "FORMAL_REVISION_REQUEST", correction_action: "CORRECT", title: "Revision request", is_mandatory: true }
          : { feedback_type: "GENERAL_COMMENT", correction_action: "NONE", title: "Comment" };
    openFeedbackFor(row, {
      ...preset,
      selected_text: contextualSelection.text,
      location: { page_number: contextualSelection.page, rects: contextualSelection.rects },
    });
  };

  const drawStart = (event: ReactPointerEvent, page: number) => {
    if (!canEdit || !overlayInteractive) return;
    event.preventDefault();
    const point = pointFromEvent(event, page);
    setDrawing({ page, start: point, points: [point] });
    (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };

  const drawMove = (event: ReactPointerEvent) => {
    if (!drawing) return;
    event.preventDefault();
    setDrawing((current) => (current ? { ...current, points: [...current.points, pointFromEvent(event, current.page)] } : current));
  };

  const drawEnd = () => {
    if (!drawing || tool === "SELECT" || tool === "ERASER") return;
    const current = drawing;
    setDrawing(null);
    const end = current.points[current.points.length - 1] ?? current.start;
    const width = Math.max(0.02, Math.abs(end.x - current.start.x));
    const height = Math.max(0.02, Math.abs(end.y - current.start.y));
    const x = Math.min(current.start.x, end.x);
    const y = Math.min(current.start.y, end.y);
    const geometry = tool === "PEN" ? {} : { x, y, width, height, start: current.start, end };
    const row = addAnnotation(current.page, tool, geometry, null, tool === "PEN" ? { points: current.points } : {}, defaultColorForTool(tool));
    if (tool === "STICKY_NOTE") openFeedbackFor(row);
  };

  const updateAnnotation = (changes: Partial<Annotation>) => {
    if (!selectedAnnotation) return;
    setAnnotations((rows) => rows.map((row) => (row.id === selectedAnnotation.id ? { ...row, ...changes } : row)));
    setDirty(true);
  };

  const saveSelectedAnnotation = async () => {
    if (!selectedAnnotation || !canEdit) return;
    if (selectedAnnotation.id < 0) {
      await saveAll(false);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const saved = await requestJson<Annotation>(reviewRoot + "/annotations/" + selectedAnnotation.id, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(geometryPayload(selectedAnnotation)),
      });
      setAnnotations((rows) => rows.map((row) => (row.id === saved.id ? saved : row)));
      setDirty(false);
      setMessage("Annotation saved.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The annotation could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const removeAnnotation = (row: Annotation) => {
    if (!canEdit) return;
    if (row.id < 0) {
      commit(annotations.filter((item) => item.id !== row.id));
    } else {
      commit(annotations.map((item) => (item.id === row.id ? { ...item, publication_status: "WITHDRAWN" } : item)));
    }
    setSelectedAnnotationId(null);
    setContextualSelection(null);
    setMessage("Annotation removed from the draft.");
  };

  const eraseSelected = () => {
    if (selectedAnnotation) removeAnnotation(selectedAnnotation);
  };

  const cancelFeedbackForm = () => {
    if (editingFeedbackId === null && selectedAnnotation && selectedAnnotation.id < 0 && isEmptyTextAnnotation(selectedAnnotation)) {
      setAnnotations((rows) => rows.filter((row) => row.id !== selectedAnnotation.id));
      setSelectedAnnotationId(null);
    }
    setEditingFeedbackId(null);
    setShowFeedbackForm(false);
    setContextualSelection(null);
    setError("");
  };

  const submitFeedback = async (event: FormEvent) => {
    event.preventDefault();
    if (!canEdit) return;
    const formal = feedbackDraft.feedback_type === "FORMAL_REVISION_REQUEST";
    if (!feedbackDraft.title.trim() || !feedbackDraft.content.trim()) {
      setError("Add a title and feedback details before saving.");
      return;
    }
    if (formal && !feedbackDraft.expected_outcome.trim()) {
      setError("Formal revision feedback needs an expected outcome.");
      return;
    }
    if (["REPLACE", "REWRITE"].includes(feedbackDraft.correction_action) && !feedbackDraft.suggested_text.trim()) {
      setError("Add suggested replacement text for this correction.");
      return;
    }
    if (feedbackDraft.correction_action === "MOVE" && !feedbackDraft.destination.trim()) {
      setError("Add a destination for a move correction.");
      return;
    }
    setSaving(true);
    setError("");
    const dueAt = feedbackDraft.due_at ? new Date(feedbackDraft.due_at).toISOString() : null;
    const body = {
      feedback_level: feedbackDraft.target_scope,
      feedback_type: feedbackDraft.feedback_type,
      correction_action: feedbackDraft.correction_action,
      title: feedbackDraft.title.trim(),
      content: feedbackDraft.content.trim(),
      suggested_text: feedbackDraft.suggested_text.trim() || null,
      selected_text: feedbackDraft.selected_text.trim() || null,
      location: feedbackDraft.location,
      destination_location: feedbackDraft.destination.trim() ? { description: feedbackDraft.destination.trim() } : null,
      expected_outcome: feedbackDraft.expected_outcome.trim() || null,
      is_mandatory: feedbackDraft.is_mandatory || formal,
      priority: feedbackDraft.priority,
      due_at: dueAt,
    };
    try {
      const saved = editingFeedbackId
        ? await requestJson<Feedback>(reviewRoot + "/feedback/" + editingFeedbackId, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          })
        : await requestJson<Feedback>(reviewRoot + "/feedback", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ submission_id: submissionId, version_id: documentContext?.versionId, ...body, publish: false }),
          });
      setFeedback((rows) => (editingFeedbackId ? rows.map((row) => (row.id === saved.id ? saved : row)) : [saved, ...rows]));
      setSelectedFeedbackId(saved.id);
      const linked = selectedAnnotation ?? annotations.find((row) => row.feedback_id === saved.id) ?? null;
      if (linked) {
        const next = { ...linked, feedback_id: saved.id, color: annotationColorForFeedback(linked.annotation_type, feedbackDraft.feedback_type) };
        setAnnotations((rows) => rows.map((row) => (row.id === next.id ? next : row)));
        setDirty(true);
        if (next.id > 0) {
          await requestJson(reviewRoot + "/annotations/" + next.id, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(geometryPayload(next)),
          });
        }
      }
      setFeedbackDraft(emptyDraft(Number(saved.location?.page_number) || activePage));
      setEditingFeedbackId(null);
      setShowFeedbackForm(false);
      setContextualSelection(null);
      setMessage(editingFeedbackId ? "Feedback updated." : "Feedback added to the draft.");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Feedback could not be saved.");
    } finally {
      setSaving(false);
    }
  };

  const selectAnnotation = (row: Annotation) => {
    if (tool === "ERASER") {
      removeAnnotation(row);
      return;
    }
    setSelectedAnnotationId(row.id);
    setAnnotationNote(row.content ?? "");
    setContextualSelection(null);
    setFeedbackDraft((current) => ({ ...current, selected_text: row.selected_text ?? current.selected_text, location: annotationLocation(row) }));
    if (row.feedback_id) {
      setSelectedFeedbackId(row.feedback_id);
      scrollFeedbackCard(row.feedback_id);
    } else {
      setSelectedFeedbackId(null);
    }
    scrollToAnnotation(row);
  };

  const selectFeedback = (row: Feedback) => {
    setSelectedFeedbackId(row.id);
    const linked = annotations.find((annotation) => annotation.feedback_id === row.id && annotation.publication_status !== "WITHDRAWN") ?? null;
    if (linked) {
      setSelectedAnnotationId(linked.id);
      scrollToAnnotation(linked);
    } else {
      scrollToPage(Number(row.location?.page_number) || 1);
    }
  };

  const postMessage = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedFeedback || !threadDraft.trim()) return;
    setSaving(true);
    setError("");
    try {
      const created = await requestJson<FeedbackMessage>(reviewRoot + "/feedback/" + selectedFeedback.id + "/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: threadDraft.trim() }),
      });
      setFeedback((rows) => rows.map((row) => (row.id === selectedFeedback.id ? { ...row, messages: [...row.messages, created] } : row)));
      setThreadDraft("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The feedback reply could not be sent.");
    } finally {
      setSaving(false);
    }
  };

  const markAddressed = async () => {
    if (!selectedFeedback || canEdit) return;
    try {
      const updated = await requestJson<Feedback>(reviewRoot + "/feedback/" + selectedFeedback.id + "/addressed", { method: "POST" });
      setFeedback((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The feedback status could not be updated.");
    }
  };

  const verifyFeedback = async () => {
    if (!selectedFeedback || !canEdit) return;
    try {
      const updated = await requestJson<Feedback>(reviewRoot + "/feedback/" + selectedFeedback.id + "/verify", { method: "POST" });
      setFeedback((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The feedback could not be verified.");
    }
  };

  const undoChange = () => {
    const previous = undo.at(-1);
    if (!previous) return;
    setRedo((current) => [...current, annotations]);
    setAnnotations(previous);
    setUndo((current) => current.slice(0, -1));
    setDirty(true);
  };

  const redoChange = () => {
    const next = redo.at(-1);
    if (!next) return;
    setUndo((current) => [...current, annotations]);
    setAnnotations(next);
    setRedo((current) => current.slice(0, -1));
    setDirty(true);
  };

  const findText = (event: FormEvent) => {
    event.preventDefault();
    if (search.trim()) (window as Window & { find?: (text: string) => boolean }).find?.(search.trim());
  };

  const fitPage = () => {
    const page = pageRefs.current[activePage];
    const scroll = scrollRef.current;
    if (!page || !scroll) return;
    setZoom(Math.max(0.55, Math.min(1.5, ((scroll.clientHeight - 40) / page.getBoundingClientRect().height) * zoom)));
  };

  const requestClose = () => {
    if (canEdit && dirty) setClosePrompt(true);
    else onClose();
  };

  const saveAndClose = async () => {
    if (await saveAll(false)) onClose();
  };

  const decideSubmission = async (decision: "approve" | "request-replacement" | "reject") => {
    if (!onDecision) return;
    const comment = decisionComment.trim();
    if (decision !== "approve" && !comment) {
      setError("Add a correction or rejection reason before recording this decision.");
      return;
    }
    if (!(await saveAll(true))) return;
    try {
      setSaving(true);
      await onDecision(decision, comment);
      onClose();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The submission decision could not be recorded.");
    } finally {
      setSaving(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement;
      const editing = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable;
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        if (canEdit) void saveAll(false);
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "z" && !editing) {
        event.preventDefault();
        undoChange();
        return;
      }
      if (((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "y") || ((event.metaKey || event.ctrlKey) && event.shiftKey && event.key.toLowerCase() === "z")) {
        event.preventDefault();
        redoChange();
        return;
      }
      if (editing) return;
      const shortcut: Record<string, ReviewTool> = { v: "SELECT", h: "HIGHLIGHT", u: "UNDERLINE", p: "PEN", t: "TEXT_BOX", e: "ERASER" };
      if (canEdit && shortcut[event.key.toLowerCase()]) {
        event.preventDefault();
        const nextTool = shortcut[event.key.toLowerCase()];
        setTool(nextTool);
        setColor(defaultColorForTool(nextTool));
      }
      if (event.key === "Delete" && canEdit) eraseSelected();
      if (event.key === "Escape" && showFeedbackForm) cancelFeedbackForm();
      else if (event.key === "Escape") requestClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  return (
    <ModalPortal>
      <div className="review-workspace" role="dialog" aria-modal="true" aria-label={"Review " + title}>
        <header className="review-workspace__header">
          <div className="review-workspace__identification">
            <span className="review-workspace__title-icon"><FileText size={19} /></span>
            <div>
              <h1>{documentContext ? "Document Review" : "Proposal Review - Module 6"}</h1>
              <p>{title} <span>·</span> Version {version}</p>
            </div>
          </div>
          <div className="review-workspace__header-actions">
            <span className={"review-workspace__save-state" + (dirty ? " is-dirty" : "")}>
              {saving ? "Saving..." : dirty ? "Unsaved changes" : <><CheckCircle2 size={14} /> All saved</>}
            </span>
            {canEdit && <>
              <button type="button" className="review-workspace__draft-button" onClick={() => void saveAll(false)} disabled={saving}><Save size={15} /> Save draft</button>
              <button type="button" className="review-workspace__publish" onClick={() => void saveAll(true)} disabled={saving}><Send size={15} /> Publish feedback</button>
              {documentContext && onDecision && <>
                <button type="button" className="review-workspace__draft-button" onClick={() => void decideSubmission("request-replacement")} disabled={saving}>Request changes</button>
                <button type="button" className="review-workspace__publish" onClick={() => void decideSubmission("approve")} disabled={saving}>Accept submission</button>
                <button type="button" className="review-workspace__close" onClick={() => void decideSubmission("reject")} disabled={saving}>Reject</button>
              </>}
            </>}
            <button type="button" className="review-workspace__close" onClick={requestClose}><X size={17} /> Close</button>
          </div>
        </header>

        <div className="review-workspace__toolbar">
          <div className="review-workspace__toolbar-scroll">
            {(canEdit ? reviewTools : reviewTools.slice(0, 1)).map(({ id, label, icon: Icon }) => (
              <button
                type="button"
                key={id}
                className={tool === id ? "is-active" : ""}
                onClick={() => {
                  setTool(id);
                  setColor(defaultColorForTool(id));
                  if (id !== "SELECT") setContextualSelection(null);
                }}
                title={label}
              >
                <Icon size={17} /><span>{label}</span>
              </button>
            ))}
            {canEdit && <>
              <span className="review-workspace__toolbar-divider" />
              <label className="review-workspace__color" title="Annotation color"><input type="color" value={color} onChange={(event) => setColor(event.target.value)} aria-label="Annotation color" /></label>
              <label className="review-workspace__stroke">Thickness<select value={strokeWidth} onChange={(event) => setStrokeWidth(Number(event.target.value))} aria-label="Annotation thickness"><option value="1">1 px</option><option value="2">2 px</option><option value="3">3 px</option><option value="5">5 px</option><option value="8">8 px</option></select></label>
              <button type="button" onClick={undoChange} disabled={!undo.length} title="Undo"><Undo2 size={17} /><span>Undo</span></button>
              <button type="button" onClick={redoChange} disabled={!redo.length} title="Redo"><Redo2 size={17} /><span>Redo</span></button>
            </>}
          </div>
          <div className="review-workspace__toolbar-hint">{canEdit ? "Select text or draw on the document" : "Published review marks are read-only"}</div>
        </div>

        <div className="review-workspace__body">
          <aside className="review-workspace__pages">
            <div className="review-workspace__panel-heading"><strong>Pages</strong><span>{pageCount || "-"}</span></div>
            <PdfDocument file={fileUrl || null} loading={<div className="review-workspace__thumb-loading" />} error={null}>
              <div className="review-workspace__thumbnail-list">
                {Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => {
                  const pageMarkers = new Set(feedback.filter((row) => Number(row.location?.page_number) === page).map(markerNumber));
                  return (
                    <button type="button" key={page} className={activePage === page ? "is-active" : ""} onClick={() => scrollToPage(page)}>
                      <span className="review-workspace__thumbnail">
                        <Page pageNumber={page} width={104} renderTextLayer={false} renderAnnotationLayer={false} />
                        <b>{page}</b>
                      </span>
                      <span className="review-workspace__thumbnail-meta">Page {page}{pageMarkers.size > 0 && <small>{pageMarkers.size}</small>}</span>
                    </button>
                  );
                })}
              </div>
            </PdfDocument>
          </aside>

          <main className="review-workspace__document">
            <div className="review-workspace__document-tools">
              <form onSubmit={findText}><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search document" aria-label="Search document" /></form>
              <button type="button" onClick={() => scrollToPage(activePage - 1)} disabled={activePage <= 1} title="Previous page"><ChevronLeft size={16} /></button>
              <span>Page {activePage} of {pageCount || "-"}</span>
              <button type="button" onClick={() => scrollToPage(activePage + 1)} disabled={activePage >= pageCount} title="Next page"><ChevronRight size={16} /></button>
              <button type="button" onClick={() => setZoom((value) => Math.max(0.55, value - 0.1))} title="Zoom out"><ZoomOut size={16} /></button>
              <span>{Math.round(zoom * 100)}%</span>
              <button type="button" onClick={() => setZoom((value) => Math.min(1.8, value + 0.1))} title="Zoom in"><ZoomIn size={16} /></button>
              <button type="button" onClick={() => setZoom(1)} title="Fit width">Fit width</button>
              <button type="button" onClick={fitPage} title="Fit page">Fit page</button>
              <a href={documentContext?.downloadUrl ? api + documentContext.downloadUrl : fileUrl} download={documentContext?.filename || title} className="review-workspace__download" title="Download original"><Download size={15} /></a>
            </div>
            <div
              className="review-workspace__scroll"
              ref={scrollRef}
              onScroll={() => {
                const entries = Object.entries(pageRefs.current)
                  .map(([page, node]) => ({ page: Number(page), distance: Math.abs((node?.getBoundingClientRect().top ?? 0) - (scrollRef.current?.getBoundingClientRect().top ?? 0) - 16) }))
                  .sort((left, right) => left.distance - right.distance);
                if (entries[0]) setActivePage(entries[0].page);
              }}
            >
              <PdfDocument
                file={fileUrl || null}
                loading={<p className="review-workspace__loading">Loading original document...</p>}
                error={<p className="review-workspace__error">{error || "The proposal could not be rendered."}</p>}
                onLoadSuccess={({ numPages }) => { setPageCount(numPages); setActivePage(1); }}
              >
                <div className="review-workspace__pages-stack">
                  {Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => (
                    <div
                      key={page}
                      ref={(node) => { pageRefs.current[page] = node; }}
                      className="review-workspace__page"
                      onMouseUp={() => handleTextSelection(page)}
                    >
                      <Page pageNumber={page} width={pageWidth * zoom} renderTextLayer renderAnnotationLayer={false} />
                      <svg
                        className={"review-workspace__overlay" + (overlayInteractive ? " is-interactive" : "")}
                        viewBox="0 0 1 1"
                        preserveAspectRatio="none"
                        onPointerDown={(event) => drawStart(event, page)}
                        onPointerMove={drawMove}
                        onPointerUp={drawEnd}
                        onPointerCancel={() => setDrawing(null)}
                      >
                        <defs><marker id="review-arrow" markerWidth="0.035" markerHeight="0.035" refX="0.03" refY="0.0175" orient="auto"><path d="M 0 0 L 0.035 0.0175 L 0 0.035 z" fill="currentColor" /></marker></defs>
                        {pageAnnotations(page).map((row) => (
                          <AnnotationShape key={row.id} row={row} marker={row.feedback_id ? feedbackById.get(row.feedback_id) : undefined} selected={row.id === selectedAnnotationId} onSelect={() => selectAnnotation(row)} />
                        ))}
                        {drawing?.page === page && <DrawingPreview drawing={drawing} tool={tool} color={color} strokeWidth={strokeWidth} />}
                      </svg>
                      {contextualSelection?.page === page && canEdit && <ContextualToolbar selection={contextualSelection} onAction={handleContextualAction} />}
                    </div>
                  ))}
                </div>
              </PdfDocument>
            </div>
            <footer className="review-workspace__status">Page {activePage} of {pageCount || "-"} <span>·</span> {visibleAnnotations.length} annotations <span>·</span> {message || (error ? error : "Review changes are version-scoped")}</footer>
          </main>

          <aside className="review-workspace__right">
            <div className="review-workspace__right-heading">
              <div><h2>{showFeedbackForm ? (editingFeedbackId ? "Edit Feedback" : "Add Feedback") : "Feedback & Corrections"}</h2><p>{feedback.length} feedback item{feedback.length === 1 ? "" : "s"} linked to this proposal version</p></div>
              {canEdit && !showFeedbackForm && <button type="button" onClick={() => openFeedbackFor(selectedAnnotation)}>+ Add feedback</button>}
              {showFeedbackForm && <button type="button" onClick={cancelFeedbackForm}>Back to feedback</button>}
            </div>
            {error && <p className="review-workspace__error review-workspace__error--panel" role="alert">{error}</p>}
            <div className="review-workspace__right-content">
              {documentContext && onDecision && <section className="review-decision-panel">
                <strong>Decision for this submission</strong>
                <small>{documentContext.filename} · Version {documentContext.version}</small>
                <textarea value={decisionComment} onChange={(event) => setDecisionComment(event.target.value)} rows={3} placeholder="Optional for acceptance; required for changes or rejection." aria-label="Decision feedback" />
              </section>}
              {showFeedbackForm && canEdit ? (
                <FeedbackForm draft={feedbackDraft} setDraft={setFeedbackDraft} onSubmit={submitFeedback} onCancel={cancelFeedbackForm} saving={saving} editing={editingFeedbackId !== null} />
              ) : (
                <>
                  <div className="review-feedback-filters">
                    <label><span>Type</span><select value={feedbackTypeFilter} onChange={(event) => setFeedbackTypeFilter(event.target.value as FeedbackType | "ALL")}><option value="ALL">All types</option>{feedbackTypes.slice(1).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                    <label><span>Page</span><select value={pageFilter} onChange={(event) => setPageFilter(event.target.value === "ALL" ? "ALL" : Number(event.target.value))}><option value="ALL">All pages</option>{Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => <option key={page} value={page}>Page {page}</option>)}</select></label>
                  </div>
                  <div className="review-feedback-list">
                    {filteredFeedback.map((row) => <FeedbackCard key={row.id} row={row} active={selectedFeedbackId === row.id} canEdit={canEdit} cardRef={(node) => { feedbackCardRefs.current[row.id] = node; }} onSelect={() => selectFeedback(row)} onEdit={() => editFeedback(row)} />)}
                  </div>
                  {!filteredFeedback.length && <div className="review-workspace__empty-panel"><MessageCircle size={21} /><strong>{feedback.length ? "No feedback matches these filters" : "No feedback yet"}</strong><p>{feedback.length ? "Try another feedback type or page." : canEdit ? "Select text or annotate the document to add feedback." : "Published supervisor feedback will appear here."}</p></div>}
                  {selectedAnnotation && canEdit && <section className="review-annotation-inspector"><div className="review-panel-heading"><strong>Selected annotation</strong><span>Page {selectedAnnotation.page_number}</span></div><p>{selectedAnnotation.selected_text || selectedAnnotation.annotation_type.replaceAll("_", " ")}</p>{["TEXT_BOX", "STICKY_NOTE"].includes(selectedAnnotation.annotation_type) && <textarea value={annotationNote} onChange={(event) => { setAnnotationNote(event.target.value); updateAnnotation({ content: event.target.value }); }} placeholder="Type the correction note" rows={3} />}<div className="review-inspector-actions"><button type="button" onClick={() => openFeedbackFor(selectedAnnotation)}>Add feedback</button><button type="button" onClick={() => void saveSelectedAnnotation()} disabled={saving}>Save mark</button><button type="button" className="is-danger" onClick={eraseSelected}>Erase</button></div></section>}
                  {selectedFeedback && <FeedbackThread feedback={selectedFeedback} role={role} draft={threadDraft} setDraft={setThreadDraft} onSubmit={postMessage} onAddress={markAddressed} onVerify={verifyFeedback} onEdit={() => editFeedback(selectedFeedback)} saving={saving} />}
                </>
              )}
            </div>
          </aside>
        </div>

        {closePrompt && <div className="review-workspace__confirm-backdrop"><section className="review-workspace__confirm" role="alertdialog" aria-modal="true" aria-labelledby="review-close-title"><h2 id="review-close-title">Unsaved review changes</h2><p>Save the current draft before closing this review?</p><div><button type="button" onClick={() => setClosePrompt(false)}>Continue editing</button><button type="button" className="is-danger" onClick={onClose}>Discard</button><button type="button" className="is-primary" onClick={() => void saveAndClose()} disabled={saving}>Save and close</button></div></section></div>}
      </div>
    </ModalPortal>
  );
}

function ContextualToolbar({ selection, onAction }: { selection: SelectionContext; onAction: (action: ContextAction) => void }) {
  const first = selection.rects[0];
  return <div className="review-contextual-toolbar" style={{ left: Math.min(78, Math.max(2, first.x * 100)) + "%", top: Math.max(1, selection.top * 100 - 6) + "%" }}>
    <button type="button" onClick={() => onAction("HIGHLIGHT")} title="Highlight selected text"><Highlighter size={14} /></button>
    <button type="button" onClick={() => onAction("UNDERLINE")} title="Underline selected text"><Underline size={14} /></button>
    <button type="button" onClick={() => onAction("STRIKETHROUGH")} title="Strike selected text"><Strikethrough size={14} /></button>
    <button type="button" onClick={() => onAction("ADD_COMMENT")} title="Add comment"><MessageSquare size={14} /></button>
    <button type="button" onClick={() => onAction("SUGGEST_REPLACEMENT")} title="Suggest replacement">Replace</button>
    <button type="button" onClick={() => onAction("REQUEST_CORRECTION")} title="Request correction">Request</button>
  </div>;
}

function AnnotationShape({ row, marker, selected, onSelect }: { row: Annotation; marker?: Feedback; selected: boolean; onSelect: () => void }) {
  const stroke = selected ? "#2D5BFF" : row.color;
  const width = Math.max(0.0015, row.stroke_width / 700);
  const rects = row.geometry.rects ?? [];
  const clickProps = { onClick: (event: React.MouseEvent) => { event.stopPropagation(); onSelect(); }, style: { pointerEvents: "auto" as const } };
  const number = marker ? markerNumber(marker) : null;
  const markerX = (rect: Rect) => Math.min(0.965, rect.x + rect.width + 0.012);
  const markerY = (rect: Rect) => Math.max(0.03, rect.y);
  const markerShape = (x: number, y: number) => number !== null ? <g className="review-annotation-marker"><circle cx={x} cy={y} r=".018" fill={selected ? "#2D5BFF" : row.color} /><text x={x} y={y + 0.006} textAnchor="middle" fill="#fff" fontSize=".018" fontWeight="700">{number}</text></g> : null;

  if (["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH"].includes(row.annotation_type) && rects.length) {
    return <g {...clickProps} className="review-annotation"><title>{row.selected_text || row.annotation_type}</title>{rects.map((rect, index) => row.annotation_type === "HIGHLIGHT" ? <rect key={index} {...rect} fill={row.color} opacity={selected ? 0.55 : 0.32} /> : <line key={index} x1={rect.x} y1={row.annotation_type === "STRIKETHROUGH" ? rect.y + rect.height / 2 : rect.y + rect.height} x2={rect.x + rect.width} y2={row.annotation_type === "STRIKETHROUGH" ? rect.y + rect.height / 2 : rect.y + rect.height} stroke={stroke} strokeWidth={width} />)}{markerShape(markerX(rects[0]), markerY(rects[0]))}</g>;
  }

  const { x = 0.2, y = 0.2, width: w = 0.2, height: h = 0.08, start, end } = row.geometry;
  if (row.annotation_type === "PEN" && row.drawing.points?.length) return <polyline {...clickProps} className="review-annotation" points={row.drawing.points.map((point) => point.x + "," + point.y).join(" ")} fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />;
  if (row.annotation_type === "ARROW" && start && end) return <g {...clickProps} className="review-annotation"><line x1={start.x} y1={start.y} x2={end.x} y2={end.y} stroke={stroke} strokeWidth={width} markerEnd="url(#review-arrow)" />{markerShape(Math.min(0.965, end.x), Math.max(0.03, end.y))}</g>;
  if (row.annotation_type === "CIRCLE") return <g {...clickProps} className="review-annotation"><ellipse cx={x + w / 2} cy={y + h / 2} rx={Math.max(0.01, w / 2)} ry={Math.max(0.01, h / 2)} fill="none" stroke={stroke} strokeWidth={width} />{markerShape(Math.min(0.965, x + w), Math.max(0.03, y))}</g>;
  if (row.annotation_type === "STICKY_NOTE") return <g {...clickProps} className="review-annotation review-annotation--sticky"><circle cx={x + w / 2} cy={y + h / 2} r=".018" fill={selected ? "#2D5BFF" : row.color} /><path d={"M " + (x + w * 0.31) + " " + (y + h * 0.35) + " L " + (x + w * 0.69) + " " + (y + h * 0.35) + " M " + (x + w * 0.31) + " " + (y + h * 0.5) + " L " + (x + w * 0.69) + " " + (y + h * 0.5)} stroke="#fff" strokeWidth=".003" />{number !== null && <text x={x + w / 2} y={y + h / 2 + 0.006} textAnchor="middle" fill="#fff" fontSize=".016" fontWeight="700">{number}</text>}</g>;
  if (row.annotation_type === "TEXT_BOX") return <g {...clickProps} className="review-annotation"><rect x={x} y={y} width={w} height={h} fill={row.color} opacity=".1" stroke={stroke} strokeWidth={width} />{(row.content || "").split("\n").slice(0, 6).map((line, index) => <text key={index} x={x + 0.01} y={y + 0.025 + index * 0.025} fontSize=".02" fill="#172B4D">{line.slice(0, 72)}</text>)}{markerShape(Math.min(0.965, x + w), Math.max(0.03, y))}</g>;
  return <g {...clickProps} className="review-annotation"><rect x={x} y={y} width={w} height={h} fill="none" stroke={stroke} strokeWidth={width} />{markerShape(Math.min(0.965, x + w), Math.max(0.03, y))}</g>;
}

function DrawingPreview({ drawing, tool, color, strokeWidth }: { drawing: PointDrawing; tool: ReviewTool; color: string; strokeWidth: number }) {
  const end = drawing.points[drawing.points.length - 1] ?? drawing.start;
  const x = Math.min(drawing.start.x, end.x);
  const y = Math.min(drawing.start.y, end.y);
  const width = Math.max(0.02, Math.abs(end.x - drawing.start.x));
  const height = Math.max(0.02, Math.abs(end.y - drawing.start.y));
  const stroke = Math.max(0.0015, strokeWidth / 700);
  if (tool === "PEN") return <polyline points={drawing.points.map((point) => point.x + "," + point.y).join(" ")} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" />;
  if (tool === "CIRCLE") return <ellipse cx={x + width / 2} cy={y + height / 2} rx={width / 2} ry={height / 2} fill="none" stroke={color} strokeWidth={stroke} />;
  if (tool === "ARROW") return <line x1={drawing.start.x} y1={drawing.start.y} x2={end.x} y2={end.y} stroke={color} strokeWidth={stroke} markerEnd="url(#review-arrow)" />;
  return <rect x={x} y={y} width={width} height={height} fill={tool === "TEXT_BOX" || tool === "STICKY_NOTE" ? color : "none"} fillOpacity=".12" stroke={color} strokeWidth={stroke} />;
}

function FeedbackCard({ row, active, canEdit, cardRef, onSelect, onEdit }: { row: Feedback; active: boolean; canEdit: boolean; cardRef: (node: HTMLElement | null) => void; onSelect: () => void; onEdit: () => void }) {
  const status = row.publication_status === "DRAFT" ? "Draft" : row.workflow_status === "VERIFIED" ? "Verified" : row.workflow_status === "ADDRESSED" ? "Addressed" : "Published";
  return <article ref={cardRef} className={"review-feedback-card" + (active ? " is-active" : "")}>
    <button type="button" className="review-feedback-card__select" onClick={onSelect}>
      <span className="review-feedback-card__top"><span className="review-feedback-card__identity"><b className={"review-feedback-card__marker review-feedback-card__marker--" + row.feedback_type.toLowerCase()}>{markerNumber(row)}</b><strong>{feedbackTypeLabel(row.feedback_type)}</strong></span><em className={"is-" + row.publication_status.toLowerCase()}>{status}</em></span>
      <span className="review-feedback-card__meta">{row.author.name} · {formatDateTime(row.created_at)} · Page {Number(row.location?.page_number) || "-"}</span>
      <span className="review-feedback-card__title">{row.title}</span>
      <span className="review-feedback-card__body">{row.content}</span>
      {row.selected_text && <span className="review-feedback-card__quote">“{row.selected_text}”</span>}
      <span className="review-feedback-card__badges">{row.is_mandatory && <small className="is-mandatory">Mandatory</small>}{row.priority !== "MEDIUM" && <small className={"is-priority-" + row.priority.toLowerCase()}>Priority: {priorityLabel(row.priority)}</small>}{row.due_at && <small className="is-due">Due {formatDateTime(row.due_at)}</small>}</span>
      <span className="review-feedback-card__footer"><span>{scopeLabel(row.feedback_level)}</span><span>{row.messages.length} repl{row.messages.length === 1 ? "y" : "ies"}</span></span>
    </button>
    {canEdit && <button type="button" className="review-feedback-card__edit" onClick={(event) => { event.stopPropagation(); onEdit(); }} aria-label={"Edit feedback " + markerNumber(row)} title="Edit feedback"><Edit3 size={14} /></button>}
  </article>;
}

function FeedbackForm({ draft, setDraft, onSubmit, onCancel, saving, editing }: { draft: FeedbackDraft; setDraft: (draft: FeedbackDraft) => void; onSubmit: (event: FormEvent) => void; onCancel: () => void; saving: boolean; editing: boolean }) {
  const update = <K extends keyof FeedbackDraft>(key: K, value: FeedbackDraft[K]) => setDraft({ ...draft, [key]: value });
  const formal = draft.feedback_type === "FORMAL_REVISION_REQUEST";
  const correction = draft.feedback_type === "CORRECTION" || draft.feedback_type === "EDITING_SUGGESTION" || formal;
  const changeType = (value: FeedbackType) => {
    const next = { ...draft, feedback_type: value };
    if (value === "GENERAL_COMMENT") next.correction_action = "NONE";
    if (value === "EDITING_SUGGESTION" && next.correction_action === "NONE") next.correction_action = "REPLACE";
    if (value === "FORMAL_REVISION_REQUEST") next.is_mandatory = true;
    setDraft(next);
  };
  return <form className="review-feedback-form" onSubmit={onSubmit}>
    <p className="review-form-intro">{editing ? "Update the existing document-linked feedback. Its marker and annotation relationship will remain unchanged." : "Create feedback from the selected text or annotation. It remains a draft until you publish the review."}</p>
    <label>Feedback type<select value={draft.feedback_type} onChange={(event) => changeType(event.target.value as FeedbackType)}><option value="GENERAL_COMMENT">General comment</option><option value="CORRECTION">Correction</option><option value="EDITING_SUGGESTION">Editing suggestion</option><option value="FORMAL_REVISION_REQUEST">Formal revision request</option></select></label>
    {correction && <label>Correction action<select value={draft.correction_action} onChange={(event) => update("correction_action", event.target.value as CorrectionAction)}><option value="NONE">No specific action</option><option value="REMOVE">Remove</option><option value="REPLACE">Replace</option><option value="ADD">Add</option><option value="MOVE">Move</option><option value="REWRITE">Rewrite</option><option value="EXPAND">Expand</option><option value="CORRECT">Technical correction</option><option value="FORMATTING">Formatting correction</option></select></label>}
    <fieldset><legend>Target scope</legend><label><input type="radio" checked={draft.target_scope === "PARAGRAPH"} onChange={() => update("target_scope", "PARAGRAPH")} /> Paragraph</label><label><input type="radio" checked={draft.target_scope === "SECTION"} onChange={() => update("target_scope", "SECTION")} /> Section</label><label><input type="radio" checked={draft.target_scope === "MODULE"} onChange={() => update("target_scope", "MODULE")} /> Module</label><label><input type="radio" checked={draft.target_scope === "FULL_PROPOSAL"} onChange={() => update("target_scope", "FULL_PROPOSAL")} /> Full proposal</label></fieldset>
    <label>Title<input required value={draft.title} onChange={(event) => update("title", event.target.value)} placeholder="Short feedback title" /></label>
    <label>Comment / correction details<textarea required maxLength={12000} rows={5} value={draft.content} onChange={(event) => update("content", event.target.value)} placeholder="Explain what should change and why." /></label>
    {draft.selected_text && <label>Selected text<textarea readOnly rows={3} value={draft.selected_text} /></label>}
    {["REPLACE", "REWRITE"].includes(draft.correction_action) && <label>Suggested replacement<textarea required rows={3} value={draft.suggested_text} onChange={(event) => update("suggested_text", event.target.value)} placeholder="Write the replacement text" /></label>}
    {draft.correction_action === "MOVE" && <label>Move destination<input required value={draft.destination} onChange={(event) => update("destination", event.target.value)} placeholder="e.g. Methodology, before section 2.1" /></label>}
    {formal && <label>Expected outcome<textarea required rows={3} value={draft.expected_outcome} onChange={(event) => update("expected_outcome", event.target.value)} placeholder="What must be true after the revision?" /></label>}
    {(draft.feedback_type === "CORRECTION" || formal) && <div className="review-form-grid"><label>Priority<select value={draft.priority} onChange={(event) => update("priority", event.target.value as Priority)}><option value="LOW">Low</option><option value="MEDIUM">Medium</option><option value="HIGH">High</option><option value="CRITICAL">Critical</option></select></label><label>Deadline<input type="datetime-local" value={draft.due_at} onChange={(event) => update("due_at", event.target.value)} /></label></div>}
    <label className="review-checkbox"><input type="checkbox" checked={draft.is_mandatory || formal} disabled={formal} onChange={(event) => update("is_mandatory", event.target.checked)} /> Mandatory revision</label>
    <div className="review-form-actions"><button type="button" onClick={onCancel}>Cancel</button><button type="submit" className="is-primary" disabled={saving}>{editing ? "Save changes" : "Add feedback"}</button></div>
  </form>;
}

function FeedbackThread({ feedback, role, draft, setDraft, onSubmit, onAddress, onVerify, onEdit, saving }: { feedback: Feedback; role: ReviewRole; draft: string; setDraft: (value: string) => void; onSubmit: (event: FormEvent) => void; onAddress: () => void; onVerify: () => void; onEdit: () => void; saving: boolean }) {
  return <section className="review-feedback-thread">
    <div className="review-panel-heading"><div><strong>Feedback {markerNumber(feedback)}</strong><small>{feedback.author.name} · {formatDateTime(feedback.created_at)}</small></div><span>{feedback.workflow_status.toLowerCase()}</span></div>
    <div className="review-thread-meta"><span>Page {Number(feedback.location?.page_number) || "-"}</span>{feedback.is_mandatory && <b>Mandatory</b>}{feedback.priority !== "MEDIUM" && <b>Priority: {priorityLabel(feedback.priority)}</b>}{feedback.due_at && <b>Due {formatDateTime(feedback.due_at)}</b>}</div>
    <p className="review-thread-details">{feedback.content}</p>
    {feedback.suggested_text && <p className="review-thread-outcome"><strong>Suggested replacement:</strong> {feedback.suggested_text}</p>}
    {feedback.expected_outcome && <p className="review-thread-outcome"><strong>Expected outcome:</strong> {feedback.expected_outcome}</p>}
    <div className="review-thread-messages">{feedback.messages.map((message) => <article key={message.id}><strong>{message.sender_name}</strong><small>{formatDateTime(message.created_at)}</small><p>{message.body}</p></article>)}</div>
    <form onSubmit={onSubmit} className="review-thread-form"><textarea value={draft} onChange={(event) => setDraft(event.target.value)} rows={3} placeholder="Reply in this document-linked thread" /><button type="submit" disabled={saving || !draft.trim()}><Send size={14} /> Reply</button></form>
    <div className="review-thread-actions">{role === "supervisor" && <button type="button" onClick={onEdit}>Edit feedback</button>}{role === "student" && feedback.workflow_status === "OPEN" && <button type="button" onClick={onAddress}>Mark addressed</button>}{role === "supervisor" && feedback.workflow_status === "ADDRESSED" && <button type="button" onClick={onVerify}>Verify addressed</button>}</div>
  </section>;
}
