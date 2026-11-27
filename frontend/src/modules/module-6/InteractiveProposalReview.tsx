import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type PointerEvent as ReactPointerEvent } from "react";
import { ArrowUpRight, Bell, ChevronDown, ChevronLeft, ChevronRight, Circle, Download, Eraser, FileText, Highlighter, ListChecks, MessageSquare, MoreHorizontal, MousePointer2, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, PenLine, Redo2, RotateCcw, Search, Send, Square, Strikethrough, StickyNote, TextCursorInput, Underline, Undo2, UserRound, X, ZoomIn, ZoomOut } from "lucide-react";
import { Document as PdfDocument, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "./interactive-proposal-review.css";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

type ReviewRole = "supervisor" | "student";
type ReviewTool = "SELECT" | "HIGHLIGHT" | "UNDERLINE" | "STRIKETHROUGH" | "PEN" | "RECTANGLE" | "CIRCLE" | "ARROW" | "TEXT_BOX" | "STICKY_NOTE" | "EDITING_SUGGESTION" | "REVISION_REQUEST" | "ERASER";
type ReviewTab = "COMMENTS" | "WHITEBOARD" | "REVISIONS" | "DISCUSSION";
type Rect = { x: number; y: number; width: number; height: number };
type Point = { x: number; y: number };
type Geometry = { rects?: Rect[]; x?: number; y?: number; width?: number; height?: number; start?: Point; end?: Point };
type Drawing = { points?: Point[] };
type Annotation = {
  id: number;
  submission_id: number;
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
  revision_request_id: number | null;
  created_at: string;
};
type Revision = { id: number; revision_code: string; title: string; description: string; status: string; source_version: number };

const tools: Array<{ id: ReviewTool; label: string; icon: typeof MousePointer2; textOnly?: boolean }> = [
  { id: "SELECT", label: "Select", icon: MousePointer2 },
  { id: "HIGHLIGHT", label: "Highlight", icon: Highlighter, textOnly: true },
  { id: "UNDERLINE", label: "Underline", icon: Underline, textOnly: true },
  { id: "STRIKETHROUGH", label: "Strikethrough", icon: Strikethrough, textOnly: true },
  { id: "PEN", label: "Pen", icon: PenLine },
  { id: "RECTANGLE", label: "Rectangle", icon: Square },
  { id: "CIRCLE", label: "Circle", icon: Circle },
  { id: "ARROW", label: "Arrow", icon: ArrowUpRight },
  { id: "TEXT_BOX", label: "Text box", icon: TextCursorInput },
  { id: "STICKY_NOTE", label: "Sticky note", icon: StickyNote },
  { id: "EDITING_SUGGESTION", label: "Editing suggestion", icon: MessageSquare, textOnly: true },
  { id: "REVISION_REQUEST", label: "Revision request", icon: ListChecks, textOnly: true },
  { id: "ERASER", label: "Eraser", icon: Eraser },
];

function clamp(value: number) { return Math.max(0, Math.min(1, value)); }
function apiError(payload: unknown, fallback: string) {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) return String((detail as { message: unknown }).message);
  }
  return fallback;
}
async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: "include", ...init });
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new Error(apiError(body, `Request failed (${response.status}).`));
  return body as T;
}
function rectFromClient(rect: DOMRect, page: DOMRect): Rect { return { x: clamp((rect.left - page.left) / page.width), y: clamp((rect.top - page.top) / page.height), width: clamp(rect.width / page.width), height: clamp(rect.height / page.height) }; }
function geometryPayload(annotation: Annotation) { return { submission_id: annotation.submission_id, annotation_type: annotation.annotation_type, page_number: annotation.page_number, geometry: annotation.geometry, drawing: annotation.drawing, selected_text: annotation.selected_text, content: annotation.content, suggested_text: annotation.suggested_text, color: annotation.color, stroke_width: annotation.stroke_width, publication_status: annotation.publication_status, revision_request_id: annotation.revision_request_id }; }

export function InteractiveProposalReview({ api, submissionId, title, version, role, onClose }: { api: string; submissionId: number; title: string; version: number; role: ReviewRole; onClose: () => void }) {
  const [fileUrl, setFileUrl] = useState("");
  const [pageCount, setPageCount] = useState(0);
  const [activePage, setActivePage] = useState(1);
  const [pageWidth, setPageWidth] = useState(760);
  const [zoom, setZoom] = useState(1);
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [tool, setTool] = useState<ReviewTool>("SELECT");
  const [tab, setTab] = useState<ReviewTab>("COMMENTS");
  const [color, setColor] = useState("#F5C542");
  const [strokeWidth, setStrokeWidth] = useState(2);
  const [leftOpen, setLeftOpen] = useState(true);
  const [rightOpen, setRightOpen] = useState(true);
  const [search, setSearch] = useState("");
  const [comment, setComment] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [revisionTitle, setRevisionTitle] = useState("");
  const [revisionDescription, setRevisionDescription] = useState("");
  const [revisionPriority, setRevisionPriority] = useState("MEDIUM");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [undo, setUndo] = useState<Annotation[][]>([]);
  const [redo, setRedo] = useState<Annotation[][]>([]);
  const [drawing, setDrawing] = useState<{ page: number; start: Point; points: Point[] } | null>(null);
  const pageRefs = useRef<Record<number, HTMLDivElement | null>>({});
  const fileUrlRef = useRef("");
  const localId = useRef(-1);

  const selected = useMemo(() => annotations.find((item) => item.id === selectedId) ?? null, [annotations, selectedId]);
  const pageAnnotations = useCallback((page: number) => annotations.filter((item) => item.page_number === page && item.publication_status !== "WITHDRAWN"), [annotations]);
  const overlayInteractive = role === "supervisor" && !["SELECT", "HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH", "EDITING_SUGGESTION", "REVISION_REQUEST"].includes(tool);
  const commit = useCallback((next: Annotation[]) => { setUndo((current) => [...current.slice(-30), annotations]); setRedo([]); setAnnotations(next); }, [annotations]);

  const load = useCallback(async () => {
    setError("");
    try {
      const [documentResponse, rows] = await Promise.all([
        fetch(`${api}/api/v1/proposal-compliance/reports/${submissionId}/original`, { credentials: "include" }),
        requestJson<Annotation[]>(`${api}/api/v1/supervisor-review/proposals/${submissionId}/annotations`),
      ]);
      if (!documentResponse.ok) throw new Error((await documentResponse.text()) || "The proposal document could not be opened.");
      const blobUrl = URL.createObjectURL(await documentResponse.blob());
      setFileUrl((previous) => { if (previous) URL.revokeObjectURL(previous); fileUrlRef.current = blobUrl; return blobUrl; });
      setAnnotations(rows);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "The review workspace could not be loaded."); }
  }, [api, submissionId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => {
      window.clearTimeout(timer);
      if (fileUrlRef.current) {
        URL.revokeObjectURL(fileUrlRef.current);
        fileUrlRef.current = "";
      }
    };
  }, [load]);
  useEffect(() => { const resize = () => setPageWidth(Math.max(420, Math.min(980, (window.innerWidth - (leftOpen ? 220 : 0) - (rightOpen ? 360 : 0) - 90) / zoom))); resize(); window.addEventListener("resize", resize); return () => window.removeEventListener("resize", resize); }, [leftOpen, rightOpen, zoom]);

  const scrollToPage = (page: number) => { setActivePage(page); pageRefs.current[page]?.scrollIntoView({ behavior: "smooth", block: "start" }); };
  const selectionGeometry = (page: number): { rects: Rect[]; text: string } | null => {
    const selection = window.getSelection();
    const container = pageRefs.current[page];
    if (!selection || selection.isCollapsed || !selection.rangeCount || !container) return null;
    const pageRect = container.getBoundingClientRect();
    const range = selection.getRangeAt(0);
    const rects = Array.from(range.getClientRects()).map((rect) => rectFromClient(rect, pageRect)).filter((rect) => rect.width > 0.002 && rect.height > 0.002);
    const text = selection.toString().trim();
    return rects.length && text ? { rects, text } : null;
  };
  const addAnnotation = (page: number, nextTool: ReviewTool, geometry: Geometry, selectedText: string | null = null) => {
    const row: Annotation = { id: localId.current--, submission_id: submissionId, author_name: "You", annotation_type: nextTool, page_number: page, geometry, drawing: {}, selected_text: selectedText, content: null, suggested_text: null, color, stroke_width: strokeWidth, publication_status: role === "student" ? "DRAFT" : "DRAFT", revision_request_id: null, created_at: new Date().toISOString() };
    commit([...annotations, row]); setSelectedId(row.id); setTab("COMMENTS"); setMessage("Draft annotation created. Save or publish it from the review header.");
    return row.id;
  };
  const handleTextSelection = (page: number) => {
    if (role !== "supervisor" || ["SELECT", "PEN", "RECTANGLE", "CIRCLE", "ARROW", "TEXT_BOX", "STICKY_NOTE", "ERASER"].includes(tool)) return;
    const selection = selectionGeometry(page);
    if (!selection) return;
    addAnnotation(page, tool, { rects: selection.rects }, selection.text);
    window.getSelection()?.removeAllRanges();
  };
  const pointFromEvent = (event: ReactPointerEvent, page: number): Point => { const rect = pageRefs.current[page]?.getBoundingClientRect(); if (!rect) return { x: 0, y: 0 }; return { x: clamp((event.clientX - rect.left) / rect.width), y: clamp((event.clientY - rect.top) / rect.height) }; };
  const drawStart = (event: ReactPointerEvent, page: number) => {
    if (role !== "supervisor" || tool === "SELECT" || ["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH", "EDITING_SUGGESTION", "REVISION_REQUEST"].includes(tool)) return;
    const point = pointFromEvent(event, page); setDrawing({ page, start: point, points: [point] }); (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
  };
  const drawMove = (event: ReactPointerEvent) => { if (!drawing) return; setDrawing((current) => current ? { ...current, points: [...current.points, pointFromEvent(event, current.page)] } : current); };
  const drawEnd = () => {
    if (!drawing) return;
    const current = drawing; setDrawing(null);
    let annotationId: number | null = null;
    if (tool === "PEN") annotationId = addAnnotation(current.page, "PEN", {}, null);
    else { const end = current.points[current.points.length - 1] ?? current.start; addAnnotation(current.page, tool, { x: Math.min(current.start.x, end.x), y: Math.min(current.start.y, end.y), width: Math.abs(end.x - current.start.x), height: Math.abs(end.y - current.start.y), start: current.start, end }, null); }
    if (annotationId !== null) setAnnotations((rows) => rows.map((row) => row.id === annotationId ? { ...row, drawing: { points: current.points } } : row));
  };
  const eraseSelected = () => { if (!selected || role !== "supervisor") return; commit(annotations.map((row) => row.id === selected.id ? { ...row, publication_status: "WITHDRAWN" } : row)); setSelectedId(null); };
  const saveAll = async (publish: boolean) => {
    if (role !== "supervisor") return;
    setSaving(true); setError(""); setMessage("");
    try {
      let rows = [...annotations];
      for (const row of rows.filter((item) => item.publication_status !== "WITHDRAWN")) {
        if (row.id < 0) {
          const saved = await requestJson<Annotation>(`${api}/api/v1/supervisor-review/proposals/${submissionId}/annotations`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...geometryPayload({ ...row, publication_status: publish ? "PUBLISHED" : "DRAFT" }), submission_id: submissionId }) });
          rows = rows.map((item) => item.id === row.id ? saved : item);
        } else if (publish && row.publication_status === "DRAFT") {
          const saved = await requestJson<Annotation>(`${api}/api/v1/supervisor-review/annotations/${row.id}/publish`, { method: "POST" });
          rows = rows.map((item) => item.id === row.id ? saved : item);
        }
      }
      for (const row of annotations.filter((item) => item.publication_status === "WITHDRAWN" && item.id > 0)) await requestJson(`${api}/api/v1/supervisor-review/annotations/${row.id}/withdraw`, { method: "POST" });
      setAnnotations(rows); setMessage(publish ? "Feedback published and students have been notified." : "Draft annotations saved.");
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Annotations could not be saved."); }
    finally { setSaving(false); }
  };
  const saveSelected = async () => {
    if (!selected || selected.id < 0 || role !== "supervisor") return saveAll(false);
    setSaving(true); setError("");
    try { const saved = await requestJson<Annotation>(`${api}/api/v1/supervisor-review/annotations/${selected.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(geometryPayload(selected)) }); setAnnotations((rows) => rows.map((row) => row.id === saved.id ? saved : row)); setMessage("Annotation saved."); }
    catch (caught) { setError(caught instanceof Error ? caught.message : "Annotation could not be saved."); }
    finally { setSaving(false); }
  };
  const createRevision = async (event: FormEvent) => {
    event.preventDefault(); if (role !== "supervisor" || !revisionTitle.trim() || !revisionDescription.trim()) return;
    setSaving(true); setError("");
    try {
      const revision = await requestJson<Revision>(`${api}/api/v1/supervisor-review/revision-requests`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ source_submission_id: submissionId, title: revisionTitle.trim(), description: revisionDescription.trim(), priority: revisionPriority, target_level: "FULL_PROPOSAL" }) });
      if (selected) setAnnotations((rows) => rows.map((row) => row.id === selected.id ? { ...row, revision_request_id: revision.id, content: revisionDescription.trim(), annotation_type: "REVISION_REQUEST" } : row));
      setRevisionTitle(""); setRevisionDescription(""); setTab("REVISIONS"); setMessage(`${revision.revision_code} created. Save or publish the linked marker.`);
    } catch (caught) { setError(caught instanceof Error ? caught.message : "Revision request could not be created."); }
    finally { setSaving(false); }
  };
  const findText = (event: FormEvent) => { event.preventDefault(); if (search.trim()) (window as Window & { find?: (text: string) => boolean }).find?.(search.trim()); };
  const undoChange = () => { const previous = undo.at(-1); if (!previous) return; setRedo((current) => [...current, annotations]); setAnnotations(previous); setUndo((current) => current.slice(0, -1)); };
  const redoChange = () => { const next = redo.at(-1); if (!next) return; setUndo((current) => [...current, annotations]); setAnnotations(next); setRedo((current) => current.slice(0, -1)); };
  const updateSelected = (changes: Partial<Annotation>) => { if (!selected) return; setAnnotations((rows) => rows.map((row) => row.id === selected.id ? { ...row, ...changes } : row)); };

  return <div className="review-workspace" role="dialog" aria-modal="true" aria-label={`Review ${title}`}>
    <header className="review-workspace__header"><div className="review-workspace__brand"><span className="review-workspace__brand-mark">F</span><strong>FYPHub</strong></div><div className="review-workspace__breadcrumb"><span>Proposal Review</span><ChevronRight size={14} /><strong>Review Workspace</strong></div><div className="review-workspace__account"><button type="button" className="review-workspace__icon-button" aria-label="Notifications" onClick={() => setMessage("No new workspace notifications.")}><Bell size={18} /><i /></button><span className="review-workspace__avatar"><UserRound size={16} /></span><span className="review-workspace__account-copy"><strong>{role === "supervisor" ? "Supervisor" : "Student"}</strong><small>{role === "supervisor" ? "Reviewer account" : "Group member"}</small></span><ChevronDown size={16} /><button type="button" className="review-workspace__close" aria-label="Close review workspace" onClick={onClose}><X size={17} /></button></div></header>
    <div className="review-workspace__subheader"><div className="review-workspace__title-wrap"><span className="review-workspace__title-icon"><FileText size={20} /></span><div><h1>Proposal Review Workspace</h1><p>Group workspace <b>·</b> {title} <b>·</b> FYPHub proposal review</p></div></div><div className="review-workspace__review-actions"><label className="review-workspace__version">Version <select value={version} onChange={() => setMessage("This submitted version is locked for review.")}><option value={version}>Version {version} · Submitted</option></select><ChevronDown size={14} /></label><span className="review-workspace__status-pill">Under review</span>{role === "supervisor" && <><button type="button" className="review-workspace__draft-button" onClick={() => void saveAll(false)} disabled={saving}>Save draft</button><button type="button" className="review-workspace__publish" onClick={() => void saveAll(true)} disabled={saving}><Send size={15} /> Publish feedback</button></>}<button type="button" className="review-workspace__icon-button review-workspace__more" aria-label="More review actions" onClick={() => setMessage("Review actions are available from the toolbar and tabs.")}><MoreHorizontal size={18} /></button></div></div>
    <div className="review-workspace__toolbar"><div className="review-workspace__toolbar-scroll"><button type="button" className={tool === "SELECT" ? "is-active" : ""} onClick={() => setTool("SELECT")} aria-label="Select tool"><MousePointer2 size={16} /><span>Select</span></button>{tools.filter(({ id }) => id !== "SELECT").map(({ id, label, icon: Icon }) => <button key={id} type="button" className={tool === id ? "is-active" : ""} onClick={() => setTool(id)} disabled={role === "student"} title={label}><Icon size={16} /><span>{label.replace("Editing suggestion", "Comment").replace("Revision request", "Revision")}</span></button>)}<span className="review-workspace__toolbar-divider" /><label className="review-workspace__color" title="Annotation color"><input type="color" value={color} onChange={(event) => setColor(event.target.value)} disabled={role === "student"} /></label><label className="review-workspace__stroke">{strokeWidth} px <select value={strokeWidth} onChange={(event) => setStrokeWidth(Number(event.target.value))} disabled={role === "student"}><option value="1">1 px</option><option value="2">2 px</option><option value="4">4 px</option><option value="8">8 px</option></select></label><button type="button" onClick={undoChange} disabled={!undo.length} title="Undo"><Undo2 size={16} /></button><button type="button" onClick={redoChange} disabled={!redo.length} title="Redo"><Redo2 size={16} /></button></div><div className="review-workspace__toolbar-end"><button type="button" onClick={() => setLeftOpen((value) => !value)} aria-label="Toggle page thumbnails">{leftOpen ? <PanelLeftClose size={17} /> : <PanelLeftOpen size={17} />}</button><button type="button" onClick={() => setRightOpen((value) => !value)} aria-label="Toggle review panel">{rightOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}</button></div></div>
    <div className={`review-workspace__body${!leftOpen ? " is-left-collapsed" : ""}${!rightOpen ? " is-right-collapsed" : ""}`}>
      {leftOpen && <aside className="review-workspace__pages"><div className="review-workspace__panel-heading"><strong>Pages</strong><span>{pageCount || "—"}</span><button type="button" onClick={() => setLeftOpen(false)} aria-label="Close pages panel"><X size={14} /></button></div><PdfDocument file={fileUrl || null} loading={<div className="review-workspace__thumb-loading" />} error={null}><div className="review-workspace__thumbnail-list">{Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => <button type="button" key={page} className={activePage === page ? "is-active" : ""} onClick={() => scrollToPage(page)}><span className="review-workspace__thumbnail"><Page pageNumber={page} width={104} renderTextLayer={false} renderAnnotationLayer={false} /><b>{page}</b></span><span className="review-workspace__thumbnail-meta">Page {page}{pageAnnotations(page).length ? <small>{pageAnnotations(page).length}</small> : null}</span></button>)}</div></PdfDocument></aside>}
      <main className="review-workspace__document"><div className="review-workspace__document-tools"><form onSubmit={findText}><Search size={15} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search document" aria-label="Search document" /></form><button type="button" onClick={() => scrollToPage(Math.max(1, activePage - 1))} title="Previous page"><ChevronLeft size={16} /></button><span>Page {activePage} of {pageCount || "—"}</span><button type="button" onClick={() => scrollToPage(Math.min(pageCount || 1, activePage + 1))} title="Next page"><ChevronRight size={16} /></button><button type="button" onClick={() => setZoom((value) => Math.max(.65, value - .1))} title="Zoom out"><ZoomOut size={16} /></button><span>{Math.round(zoom * 100)}%</span><button type="button" onClick={() => setZoom((value) => Math.min(1.8, value + .1))} title="Zoom in"><ZoomIn size={16} /></button><button type="button" onClick={() => setZoom(1)} title="Reset zoom"><RotateCcw size={15} /></button><a href={fileUrl} download={title} className="review-workspace__download" title="Download original"><Download size={15} /></a></div><div className="review-workspace__scroll" onScroll={() => { const pages = Object.entries(pageRefs.current).map(([page, node]) => ({ page: Number(page), top: Math.abs((node?.getBoundingClientRect().top ?? 0) - 90) })).sort((a, b) => a.top - b.top); if (pages[0]) setActivePage(pages[0].page); }}><PdfDocument file={fileUrl || null} loading={<p className="review-workspace__loading">Loading original document…</p>} error={<p className="review-workspace__error">{error || "The proposal could not be rendered."}</p>} onLoadSuccess={({ numPages }) => { setPageCount(numPages); setActivePage(1); }}><div className="review-workspace__pages-stack">{Array.from({ length: pageCount }, (_, index) => index + 1).map((page) => <div key={page} ref={(node) => { pageRefs.current[page] = node; }} className="review-workspace__page" onMouseUp={() => handleTextSelection(page)}><Page pageNumber={page} width={pageWidth * zoom} renderTextLayer renderAnnotationLayer={false} /><svg className={`review-workspace__overlay${overlayInteractive ? " is-interactive" : ""}`} viewBox="0 0 1 1" preserveAspectRatio="none" onPointerDown={(event) => drawStart(event, page)} onPointerMove={drawMove} onPointerUp={drawEnd}><defs><marker id="review-arrow" markerWidth="0.02" markerHeight="0.02" refX="0.018" refY="0.01" orient="auto"><path d="M 0 0 L 0.02 0.01 L 0 0.02 z" fill="currentColor" /></marker></defs>{pageAnnotations(page).map((row) => <AnnotationShape key={row.id} row={row} selected={row.id === selectedId} onSelect={() => { setSelectedId(row.id); setTab(row.annotation_type === "REVISION_REQUEST" ? "REVISIONS" : "COMMENTS"); }} />)}{drawing?.page === page && <DrawingPreview drawing={drawing} tool={tool} color={color} strokeWidth={strokeWidth} />}</svg></div>)}</div></PdfDocument></div><footer className="review-workspace__status">Page {activePage} of {pageCount || "—"}<span>·</span>{annotations.filter((row) => row.publication_status !== "WITHDRAWN").length} annotations<span>·</span>{saving ? "Saving…" : message || "All changes saved"}</footer></main>
      {rightOpen && <aside className="review-workspace__right"><div className="review-workspace__tabs">{(["COMMENTS", "WHITEBOARD", "REVISIONS", "DISCUSSION"] as ReviewTab[]).map((item) => <button type="button" key={item} className={tab === item ? "is-active" : ""} onClick={() => setTab(item)}>{item === "COMMENTS" ? `Comments (${annotations.filter((row) => row.publication_status !== "WITHDRAWN").length})` : item === "REVISIONS" ? `Revisions (${annotations.filter((row) => row.annotation_type === "REVISION_REQUEST" && row.publication_status !== "WITHDRAWN").length})` : item[0] + item.slice(1).toLowerCase()}</button>)}</div>{error && <p className="review-workspace__error review-workspace__error--panel">{error}</p>}{tab === "COMMENTS" && <CommentsPanel role={role} rows={annotations.filter((row) => row.publication_status !== "WITHDRAWN")} selected={selected} comment={comment} suggestion={suggestion} setComment={setComment} setSuggestion={setSuggestion} onSelect={(row) => { setSelectedId(row.id); scrollToPage(row.page_number); }} onUpdate={updateSelected} onSave={() => void saveSelected()} onErase={eraseSelected} saving={saving} onAddFeedback={() => { setTool("EDITING_SUGGESTION"); setMessage("Select text in the document to add a comment."); }} />}{tab === "WHITEBOARD" && <div className="review-workspace__empty-tab"><PenLine size={24} /><strong>Whiteboard layer</strong><p>Use the Pen, Rectangle, Circle and Arrow tools on the document canvas. These marks are saved with the review draft.</p><button type="button" onClick={() => { setTab("COMMENTS"); setTool("PEN"); setMessage("Draw on the document to add a whiteboard mark."); }}>Start drawing</button></div>}{tab === "REVISIONS" && <RevisionPanel rows={annotations.filter((row) => row.annotation_type === "REVISION_REQUEST" && row.publication_status !== "WITHDRAWN")} selected={selected} title={revisionTitle} description={revisionDescription} priority={revisionPriority} setTitle={setRevisionTitle} setDescription={setRevisionDescription} setPriority={setRevisionPriority} onSubmit={createRevision} onSelect={(row) => { setSelectedId(row.id); scrollToPage(row.page_number); }} saving={saving} />}{tab === "DISCUSSION" && <div className="review-workspace__empty-tab"><MessageSquare size={24} /><strong>Document-linked discussion</strong><p>Use a revision marker or create a revision request to continue the formal discussion with the group.</p><button type="button" onClick={() => setTab("REVISIONS")}>Open revisions</button></div>}</aside>}
    </div>
  </div>;
}

function AnnotationShape({ row, selected, onSelect }: { row: Annotation; selected: boolean; onSelect: () => void }) {
  const stroke = selected ? "#2D5BFF" : row.color;
  const width = Math.max(.0015, row.stroke_width / 700);
  const rects = row.geometry.rects ?? [];
  if (["HIGHLIGHT", "UNDERLINE", "STRIKETHROUGH", "EDITING_SUGGESTION", "REVISION_REQUEST"].includes(row.annotation_type) && rects.length) return <g onClick={(event) => { event.stopPropagation(); onSelect(); }} className="review-annotation"><title>{row.content || row.selected_text || row.annotation_type}</title>{rects.map((rect, index) => row.annotation_type === "HIGHLIGHT" ? <rect key={index} {...rect} fill={row.color} opacity={selected ? .5 : .32} /> : <line key={index} x1={rect.x} y1={row.annotation_type === "STRIKETHROUGH" ? rect.y + rect.height / 2 : rect.y + rect.height} x2={rect.x + rect.width} y2={row.annotation_type === "STRIKETHROUGH" ? rect.y + rect.height / 2 : rect.y + rect.height} stroke={stroke} strokeWidth={width} />)}</g>;
  const { x = .2, y = .2, width: w = .2, height: h = .08, start, end } = row.geometry;
  if (row.annotation_type === "PEN" && row.drawing.points?.length) return <polyline onClick={onSelect} className="review-annotation" points={row.drawing.points.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round" />;
  if (row.annotation_type === "ARROW" && start && end) return <g onClick={onSelect} className="review-annotation"><line x1={start.x} y1={start.y} x2={end.x} y2={end.y} stroke={stroke} strokeWidth={width} markerEnd="url(#review-arrow)" /></g>;
  if (row.annotation_type === "CIRCLE") return <ellipse onClick={onSelect} className="review-annotation" cx={x + w / 2} cy={y + h / 2} rx={Math.max(.01, w / 2)} ry={Math.max(.01, h / 2)} fill="none" stroke={stroke} strokeWidth={width} />;
  if (row.annotation_type === "TEXT_BOX" || row.annotation_type === "STICKY_NOTE") return <g onClick={onSelect} className="review-annotation"><rect x={x} y={y} width={w} height={h} fill={row.color} opacity={.18} stroke={stroke} strokeWidth={width} /><text x={x + .01} y={y + .035} fontSize=".025" fill="#172b4d">{(row.content || "Add note").slice(0, 60)}</text></g>;
  return <rect onClick={onSelect} className="review-annotation" x={x} y={y} width={w} height={h} fill="none" stroke={stroke} strokeWidth={width} />;
}

function DrawingPreview({ drawing, tool, color, strokeWidth }: { drawing: { start: Point; points: Point[] }; tool: ReviewTool; color: string; strokeWidth: number }) {
  const end = drawing.points[drawing.points.length - 1] ?? drawing.start;
  const x = Math.min(drawing.start.x, end.x); const y = Math.min(drawing.start.y, end.y); const width = Math.abs(end.x - drawing.start.x); const height = Math.abs(end.y - drawing.start.y); const stroke = Math.max(.0015, strokeWidth / 700);
  if (tool === "PEN") return <polyline points={drawing.points.map((point) => `${point.x},${point.y}`).join(" ")} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round" />;
  if (tool === "CIRCLE") return <ellipse cx={x + width / 2} cy={y + height / 2} rx={Math.max(.01, width / 2)} ry={Math.max(.01, height / 2)} fill="none" stroke={color} strokeWidth={stroke} />;
  if (tool === "ARROW") return <line x1={drawing.start.x} y1={drawing.start.y} x2={end.x} y2={end.y} stroke={color} strokeWidth={stroke} markerEnd="url(#review-arrow)" />;
  return <rect x={x} y={y} width={width} height={height} fill={tool === "TEXT_BOX" ? color : "none"} fillOpacity={.12} stroke={color} strokeWidth={stroke} />;
}

function CommentsPanel({ role, rows, selected, comment, suggestion, setComment, setSuggestion, onSelect, onUpdate, onSave, onErase, saving, onAddFeedback }: { role: ReviewRole; rows: Annotation[]; selected: Annotation | null; comment: string; suggestion: string; setComment: (value: string) => void; setSuggestion: (value: string) => void; onSelect: (row: Annotation) => void; onUpdate: (changes: Partial<Annotation>) => void; onSave: () => void; onErase: () => void; saving: boolean; onAddFeedback: () => void }) {
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [pageFilter, setPageFilter] = useState("ALL");
  const filtered = rows.filter((row) => (typeFilter === "ALL" || row.annotation_type === typeFilter) && (pageFilter === "ALL" || row.page_number === Number(pageFilter)));
  const types = Array.from(new Set(rows.map((row) => row.annotation_type)));
  const pages = Array.from(new Set(rows.map((row) => row.page_number))).sort((a, b) => a - b);
  return <div className="review-panel-content"><div className="review-panel-heading"><div><strong>Feedback &amp; comments</strong><small>Document-linked review notes</small></div><span>{filtered.length}</span></div><div className="review-panel-actions"><select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filter comments by type"><option value="ALL">All types</option>{types.map((type) => <option key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select><select value={pageFilter} onChange={(event) => setPageFilter(event.target.value)} aria-label="Filter comments by page"><option value="ALL">All pages</option>{pages.map((page) => <option key={page} value={page}>Page {page}</option>)}</select>{role === "supervisor" && <button type="button" className="review-panel-add" onClick={onAddFeedback}>+ Add feedback</button>}</div>{!filtered.length && <p className="review-workspace__muted">No document annotations match these filters.</p>}<div className="review-comments-list">{filtered.map((row) => <button type="button" key={row.id} className={`review-comment-card${selected?.id === row.id ? " is-active" : ""}`} onClick={() => onSelect(row)}><span className="review-comment-card__top"><span className="review-comment-marker">{row.page_number}</span><span><strong>{row.annotation_type.replaceAll("_", " ")}</strong>{row.annotation_type === "REVISION_REQUEST" && <em>Mandatory</em>}</span><small>Page {row.page_number}</small></span><span className="review-comment-card__author"><span className="review-comment-card__avatar"><UserRound size={13} /></span><span><b>{row.author_name}</b><small>{new Date(row.created_at).toLocaleString()}</small></span><MoreHorizontal size={16} /></span><span className="review-comment-card__body">{row.content || row.selected_text || "Document marker"}</span>{row.suggested_text && <span className="review-comment-card__suggestion">Suggested: {row.suggested_text}</span>}</button>)}</div>{role === "supervisor" && selected && <section className="review-editor"><div className="review-editor__meta">Page {selected.page_number} · {selected.publication_status.toLowerCase()}</div><textarea value={comment || selected.content || ""} onChange={(event) => { setComment(event.target.value); onUpdate({ content: event.target.value }); }} placeholder="Write a document-linked comment" rows={4} /><textarea value={suggestion || selected.suggested_text || ""} onChange={(event) => { setSuggestion(event.target.value); onUpdate({ suggested_text: event.target.value }); }} placeholder="Suggested replacement text (optional)" rows={3} /><div className="review-editor__actions"><button type="button" onClick={onSave} disabled={saving}>Save changes</button><button type="button" onClick={onErase} disabled={saving} className="is-danger">Withdraw</button></div></section>}</div>;
}

function RevisionPanel({ rows, selected, title, description, priority, setTitle, setDescription, setPriority, onSubmit, onSelect, saving }: { rows: Annotation[]; selected: Annotation | null; title: string; description: string; priority: string; setTitle: (value: string) => void; setDescription: (value: string) => void; setPriority: (value: string) => void; onSubmit: (event: FormEvent) => void; onSelect: (row: Annotation) => void; saving: boolean }) {
  return <div className="review-panel-content"><div className="review-panel-heading"><strong>Revision requests</strong><span>{rows.length}</span></div>{rows.map((row) => <button type="button" key={row.id} className={selected?.id === row.id ? "review-revision-row is-active" : "review-revision-row"} onClick={() => onSelect(row)}><strong>{row.revision_request_id ? `REV-${row.revision_request_id}` : "Draft request"}</strong><small>Page {row.page_number} · {row.content || row.selected_text || "No instruction yet"}</small></button>)}<form className="review-revision-form" onSubmit={onSubmit}><h3>Create mandatory revision</h3><p>Select text or draw a marker first to link the request to that document location.</p><input required value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Revision title" /><textarea required value={description} onChange={(event) => setDescription(event.target.value)} placeholder="What must the student change?" rows={4} /><select value={priority} onChange={(event) => setPriority(event.target.value)}><option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select><button type="submit" disabled={saving}><ListChecks size={15} /> Create revision request</button></form></div>;
}
