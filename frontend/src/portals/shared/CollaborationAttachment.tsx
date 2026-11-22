import { Download, ExternalLink, FileText } from "lucide-react";

type CollaborationAttachmentProps = {
  api: string;
  reference: string;
  kind?: string;
  payload?: Record<string, unknown>;
  caption?: string;
};

function stringValue(payload: Record<string, unknown>, key: string): string {
  const value = payload[key];
  return typeof value === "string" ? value : "";
}

function extensionOf(name: string): string {
  const extension = name.toLowerCase().split(".").pop();
  return extension && extension !== name.toLowerCase() ? extension : "";
}

export function CollaborationAttachment({ api, reference, kind = "DOCUMENT", payload = {}, caption = "" }: CollaborationAttachmentProps) {
  const url = reference.startsWith("http") ? reference : api.replace(/\/$/, "") + reference;
  const name = stringValue(payload, "name") || "Shared file";
  const mime = stringValue(payload, "mime_type").toLowerCase();
  const extension = extensionOf(name);
  const imageExtensions = ["avif", "gif", "jpeg", "jpg", "png", "svg", "webp"];
  const videoExtensions = ["avi", "m4v", "mkv", "mov", "mp4", "mpeg", "webm"];
  const audioExtensions = ["aac", "flac", "m4a", "mp3", "oga", "ogg", "wav", "weba"];
  const isImage = mime.startsWith("image/") || imageExtensions.includes(extension) || kind === "STICKER";
  const isVideo = mime.startsWith("video/") || videoExtensions.includes(extension);
  const isAudio = !isVideo && (mime.startsWith("audio/") || audioExtensions.includes(extension) || kind === "AUDIO");
  const isPdf = mime === "application/pdf" || extension === "pdf";
  const isText = mime.startsWith("text/") || ["csv", "json", "log", "md", "xml"].includes(extension);
  const hasInlinePreview = isImage || isVideo || isAudio || isPdf || isText;
  const trimmedCaption = caption.trim();

  return <div className="student-collab__attachment-card">
    {trimmedCaption && trimmedCaption !== name && <p className="student-collab__attachment-caption">{trimmedCaption}</p>}
    <div className="student-collab__attachment-preview" aria-label={`Preview of ${name}`}>
      {isImage && <img src={url} alt={name} />}
      {isVideo && <video controls playsInline preload="metadata" src={url} />}
      {isAudio && <audio controls preload="metadata" src={url} />}
      {isPdf && <iframe title={`Preview of ${name}`} src={url} />}
      {isText && <iframe title={`Preview of ${name}`} src={url} />}
      {!hasInlinePreview && <div className="student-collab__attachment-unavailable"><FileText size={24} aria-hidden /><span>Preview is not available in this browser.</span></div>}
    </div>
    <div className="student-collab__attachment-actions">
      <a href={url} target="_blank" rel="noreferrer" className="student-collab__attachment-open"><ExternalLink size={15} aria-hidden />Open</a>
      <a href={url} download={name} className="student-collab__attachment-download"><Download size={15} aria-hidden />Download</a>
    </div>
  </div>;
}
