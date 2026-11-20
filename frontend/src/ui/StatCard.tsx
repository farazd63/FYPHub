import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "./Card";

type StatCardProps = {
  label: string;
  value: ReactNode;
  hint?: string;
  icon?: LucideIcon;
  trend?: ReactNode;
  className?: string;
};

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  trend,
  className,
}: StatCardProps) {
  return (
    <Card className={["fy-stat-card", className].filter(Boolean).join(" ")}>
      <div className="fy-stat-card__head">
        <span className="fy-stat-card__label">{label}</span>
        {Icon && (
          <span className="fy-stat-card__icon" aria-hidden>
            <Icon strokeWidth={1.75} size={18} />
          </span>
        )}
      </div>
      <div className="fy-stat-card__value">{value}</div>
      {(hint || trend) && (
        <div className="fy-stat-card__foot">
          {hint && <span className="fy-stat-card__hint">{hint}</span>}
          {trend && <span className="fy-stat-card__trend">{trend}</span>}
        </div>
      )}
    </Card>
  );
}