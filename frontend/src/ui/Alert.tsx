import { AlertCircle, CheckCircle2, Info, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";

export type AlertTone = "neutral" | "success" | "warning" | "danger" | "info";

const ICONS = {
  neutral: Info,
  success: CheckCircle2,
  warning: TriangleAlert,
  danger: AlertCircle,
  info: Info,
} as const;

type AlertProps = {
  tone?: AlertTone;
  title?: string;
  children: ReactNode;
  className?: string;
  role?: "alert" | "status";
};

export function Alert({
  tone = "neutral",
  title,
  children,
  className,
  role = tone === "danger" || tone === "warning" ? "alert" : "status",
}: AlertProps) {
  const Icon = ICONS[tone];
  return (
    <div
      className={["fy-alert", `fy-alert--${tone}`, className].filter(Boolean).join(" ")}
      role={role}
    >
      <Icon className="fy-alert__icon" strokeWidth={1.75} size={18} aria-hidden />
      <div className="fy-alert__body">
        {title && <p className="fy-alert__title">{title}</p>}
        <div className="fy-alert__content">{children}</div>
      </div>
    </div>
  );
}