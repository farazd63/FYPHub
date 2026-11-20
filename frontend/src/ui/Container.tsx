import type { HTMLAttributes, ReactNode } from "react";

type ContainerProps = HTMLAttributes<HTMLDivElement> & {
  children: ReactNode;
  width?: "default" | "narrow" | "wide";
};

export function Container({
  children,
  className,
  width = "default",
  ...rest
}: ContainerProps) {
  return (
    <div
      className={[
        "fy-container",
        width !== "default" && `fy-container--${width}`,
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}