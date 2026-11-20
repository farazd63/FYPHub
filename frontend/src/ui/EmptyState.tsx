import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: LucideIcon;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({
  title,
  description,
  icon: Icon,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={["fy-empty", className].filter(Boolean).join(" ")}>
      {Icon && (
        <span className="fy-empty__icon" aria-hidden>
          <Icon strokeWidth={1.75} size={28} />
        </span>
      )}
      <h3 className="fy-empty__title">{title}</h3>
      {description && <p className="fy-empty__desc">{description}</p>}
      {action && <div className="fy-empty__action">{action}</div>}
    </div>
  );
}