import type { HTMLAttributes } from "react";

type SkeletonProps = HTMLAttributes<HTMLDivElement> & {
  width?: string | number;
  height?: string | number;
  rounded?: boolean;
};

export function Skeleton({
  className,
  width,
  height,
  rounded,
  style,
  ...rest
}: SkeletonProps) {
  return (
    <div
      className={[
        "fy-skeleton",
        rounded && "fy-skeleton--rounded",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      style={{
        width,
        height,
        ...style,
      }}
      aria-hidden
      {...rest}
    />
  );
}