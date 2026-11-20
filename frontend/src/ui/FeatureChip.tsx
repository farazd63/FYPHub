import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

type FeatureChipProps = {
  children: ReactNode;
  icon?: LucideIcon;
  active?: boolean;
  className?: string;
};

export function FeatureChip({
  children,
  icon: Icon,
  active = false,
  className,
}: FeatureChipProps) {
  return (
    <span
      className={[
        "fy-feature-chip",
        active && "fy-feature-chip--active",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      {Icon && (
        <Icon className="fy-feature-chip__icon" strokeWidth={1.75} size={14} aria-hidden />
      )}
      <span>{children}</span>
    </span>
  );
}