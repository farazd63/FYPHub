import type { ReactNode } from "react";
import { Breadcrumb, type BreadcrumbItem } from "./Breadcrumb";

type PageHeaderProps = {
  title: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  className?: string;
};

export function PageHeader({
  title,
  breadcrumbs,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header className={["fy-page-header", className].filter(Boolean).join(" ")}>
      {breadcrumbs && breadcrumbs.length > 0 && <Breadcrumb items={breadcrumbs} />}
      <div className="fy-page-header__row">
        <div className="fy-page-header__copy">
          <h1 className="fy-page-header__title">{title}</h1>
        </div>
        {actions && <div className="fy-page-header__actions">{actions}</div>}
      </div>
    </header>
  );
}
