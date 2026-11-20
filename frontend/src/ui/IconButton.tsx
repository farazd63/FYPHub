import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export type IconButtonVariant = "primary" | "secondary" | "ghost" | "danger";
export type IconButtonSize = "sm" | "md" | "lg";

function join(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
}

type IconButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  label: string;
  variant?: IconButtonVariant;
  size?: IconButtonSize;
  loading?: boolean;
  children: ReactNode;
};

export function IconButton({
  label,
  variant = "ghost",
  size = "md",
  loading = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: IconButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={join(
        "fy-icon-btn",
        `fy-icon-btn--${variant}`,
        `fy-icon-btn--${size}`,
        loading && "fy-icon-btn--loading",
        isDisabled && "fy-icon-btn--disabled",
        className,
      )}
      disabled={isDisabled}
      aria-label={label}
      title={label}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? (
        <Loader2 className="fy-icon-btn__spinner" strokeWidth={1.75} size={18} aria-hidden />
      ) : (
        children
      )}
    </button>
  );
}