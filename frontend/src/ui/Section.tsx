import type { ReactNode } from "react";

type SectionProps = {
  title?: string;
  children: ReactNode;
  className?: string;
  id?: string;
};

export function Section({
  title,
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
      {title && (
        <header className="fy-section__header">
          <h2 id={headingId} className="fy-section__title">
            {title}
          </h2>
        </header>
      )}
      <div className="fy-section__body">{children}</div>
    </section>
  );
}
