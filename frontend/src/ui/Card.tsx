import type { HTMLAttributes, ReactNode } from "react";

type CardProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  padding?: "none" | "sm" | "md" | "lg";
};

export function Card({
  children,
  className,
  padding = "md",
  ...rest
}: CardProps) {
  return (
    <div
      className={["fy-card", `fy-card--pad-${padding}`, className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}