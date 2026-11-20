import { ChevronRight } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "./Link";

export type BreadcrumbItem = {
  label: string;
  href?: string;
};

type BreadcrumbProps = {
  items: BreadcrumbItem[];
  className?: string;
};

export function Breadcrumb({ items, className }: BreadcrumbProps) {
  if (!items.length) return null;

  return (
    <nav
      className={["fy-breadcrumb", className].filter(Boolean).join(" ")}
      aria-label="Breadcrumb"
    >
      <ol className="fy-breadcrumb__list">
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={`${item.label}-${index}`} className="fy-breadcrumb__item">
              {index > 0 && (
                <ChevronRight
                  className="fy-breadcrumb__sep"
                  strokeWidth={1.75}
                  size={14}
                  aria-hidden
                />
              )}
              <Crumb item={item} isLast={isLast} />
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

function Crumb({ item, isLast }: { item: BreadcrumbItem; isLast: boolean }) {
  if (isLast || !item.href) {
    return (
      <span className="fy-breadcrumb__current" aria-current={isLast ? "page" : undefined}>
        {item.label}
      </span>
    );
  }
  return (
    <Link href={item.href} className="fy-breadcrumb__link">
      {item.label}
    </Link>
  );
}

export function BreadcrumbPage({ children }: { children: ReactNode }) {
  return <span className="fy-breadcrumb__current">{children}</span>;
}