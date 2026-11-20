import type { AnchorHTMLAttributes, ReactNode } from "react";

type LinkProps = AnchorHTMLAttributes<HTMLAnchorElement> & {
  children: ReactNode;
  external?: boolean;
};

export function Link({
  children,
  className,
  external,
  href,
  target,
  rel,
  ...rest
}: LinkProps) {
  const isExternal = external ?? (href?.startsWith("http") === true);
  const safeRel =
    rel ?? (isExternal || target === "_blank" ? "noopener noreferrer" : undefined);

  return (
    <a
      href={href}
      className={["fy-link", className].filter(Boolean).join(" ")}
      target={target ?? (isExternal ? "_blank" : undefined)}
      rel={safeRel}
      {...rest}
    >
      {children}
    </a>
  );
}