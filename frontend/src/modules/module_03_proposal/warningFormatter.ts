export type WarningSeverity = "error" | "warning" | "info";

export type FormattedWarning = {
  message: string;
  severity: WarningSeverity;
  code?: string;
  field?: string;
  raw: unknown;
};

const humanize = (value: string) =>
  value
    .replace(/[_-]+/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (character) => character.toUpperCase());

const severity = (value: unknown): WarningSeverity => {
  const normalized = typeof value === "string" ? value.toLowerCase() : "";
  if (normalized === "error" || normalized === "critical" || normalized === "high") return "error";
  if (normalized === "info" || normalized === "notice") return "info";
  return "warning";
};

const valueText = (value: unknown): string => {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.map(valueText).filter(Boolean).join(", ");
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .filter(([key]) => !["severity", "code", "field"].includes(key))
      .map(([key, nested]) => `${humanize(key)}: ${valueText(nested)}`)
      .filter((entry) => !entry.endsWith(": "))
      .join("; ");
  }
  return "";
};

export function formatWarning(raw: unknown): FormattedWarning {
  if (typeof raw === "string") {
    return { message: raw.trim() || "Warning details were not provided.", severity: "warning", raw };
  }

  if (raw && typeof raw === "object" && !Array.isArray(raw)) {
    const object = raw as Record<string, unknown>;
    const code = typeof object.code === "string" ? object.code : undefined;
    const field = typeof object.field === "string" ? object.field : undefined;
    const messageValue = object.message ?? object.issue ?? object.reason ?? object.details;
    const message = valueText(messageValue) || valueText(object);
    return {
      message: field && message && !message.toLowerCase().startsWith(field.toLowerCase()) ? `${humanize(field)}: ${message}` : message || "Warning details were not provided.",
      severity: severity(object.severity),
      code,
      field,
      raw,
    };
  }

  return { message: valueText(raw) || "Warning details were not provided.", severity: "warning", raw };
}

export const formatWarnings = (warnings: unknown[]) => warnings.map(formatWarning);

export const safeJson = (value: unknown) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Warning details could not be serialized.";
  }
};
