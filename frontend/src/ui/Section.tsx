import type { ReactNode } from "react";

type SectionProps = {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
  id?: string;
};

export function Section({
  title,
  description,
  children,
  className,
  id,
}: SectionProps) {
  const headingId = title && id ? `${id}-heading` : undefined;
  return (
    <section
      className={["fy-section", className].filter(Boolean).join(" ")}
      id={id}
      aria-labelledby={headingId}
    >
      {(title || description) && (
        <header className="fy-section__header">
          {title && (
            <h2 id={headingId} className="fy-section__title">
              {title}
            </h2>
          )}
          {description && <p className="fy-section__desc">{description}</p>}
        </header>
      )}
      <div className="fy-section__body">{children}</div>
    </section>
  );
}