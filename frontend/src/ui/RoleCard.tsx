import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Card } from "./Card";
import { Link } from "./Link";

type RoleCardProps = {
  title: string;
  description: string;
  icon?: LucideIcon;
  href?: string;
  action?: ReactNode;
  className?: string;
};

export function RoleCard({
  title,
  description,
  icon: Icon,
  href,
  action,
  className,
}: RoleCardProps) {
  return (
    <Card className={["fy-role-card", className].filter(Boolean).join(" ")}>
      <div className="fy-role-card__head">
        {Icon && (
          <span className="fy-role-card__icon" aria-hidden>
            <Icon strokeWidth={1.75} size={22} />
          </span>
        )}
        <h3 className="fy-role-card__title">{title}</h3>
      </div>
      <p className="fy-role-card__desc">{description}</p>
      {href ? (
        <Link href={href} className="fy-role-card__link">
          Open workspace
        </Link>
      ) : (
        action
      )}
    </Card>
  );
}