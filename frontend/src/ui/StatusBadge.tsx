const STATUS_LABELS = {
  NOT_SUBMITTED: "Not submitted",
  SUBMITTED: "Submitted",
  ACCEPTED: "Accepted",
  CHANGES_REQUESTED: "Changes requested",
  REJECTED: "Rejected",
  WITHDRAWN: "Withdrawn",
  ACTIVE: "Active",
  PUBLISHED: "Published",
  FORMING: "Forming",
  SCHEDULED: "Scheduled",
  DRAFT: "Draft",
  OPEN: "Open",
  CLOSED: "Closed",
  UNDER_REVIEW: "Under review",
  UPLOADED: "Submitted",
  RESUBMISSION_REQUIRED: "Changes requested",
  INACTIVE: "Inactive",
} as const;

export type StatusBadgeValue = keyof typeof STATUS_LABELS;

type StatusTone = "neutral" | "success" | "warning" | "danger" | "info" | "brand";

const STATUS_TONE: Partial<Record<StatusBadgeValue, StatusTone>> = {
  NOT_SUBMITTED: "neutral",
  SUBMITTED: "info",
  ACCEPTED: "success",
  CHANGES_REQUESTED: "warning",
  REJECTED: "danger",
  WITHDRAWN: "neutral",
  ACTIVE: "success",
  PUBLISHED: "success",
  FORMING: "info",
  SCHEDULED: "brand",
  DRAFT: "neutral",
  OPEN: "success",
  CLOSED: "neutral",
  UNDER_REVIEW: "warning",
  UPLOADED: "info",
  RESUBMISSION_REQUIRED: "warning",
  INACTIVE: "neutral",
};

type StatusBadgeProps = {
  status: StatusBadgeValue | string;
  className?: string;
};

export function formatStatusLabel(status: string): string {
  if (status in STATUS_LABELS) {
    return STATUS_LABELS[status as StatusBadgeValue];
  }
  return status
    .toLowerCase()
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const key = status as StatusBadgeValue;
  const label =
    key in STATUS_LABELS ? STATUS_LABELS[key] : formatStatusLabel(status);
  const tone = STATUS_TONE[key] ?? "neutral";

  return (
    <span
      className={["fy-status-badge", `fy-status-badge--${tone}`, className]
        .filter(Boolean)
        .join(" ")}
    >
      {label}
    </span>
  );
}