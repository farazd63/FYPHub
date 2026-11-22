import { Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "success" | "warning" | "info";
export type ButtonSize = "sm" | "md" | "lg";

function join(...parts: Array<string | false | undefined>) {
  return parts.filter(Boolean).join(" ");
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  children: ReactNode;
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className,
  children,
  type = "button",
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={join(
        "fy-btn",
        `fy-btn--${variant}`,
        `fy-btn--${size}`,
        loading && "fy-btn--loading",
        isDisabled && "fy-btn--disabled",
        className,
      )}
      disabled={isDisabled}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && (
        <Loader2 className="fy-btn__spinner" strokeWidth={1.75} size={16} aria-hidden />
      )}
      <span className={loading ? "fy-btn__label fy-btn__label--loading" : "fy-btn__label"}>
        {children}
      </span>
    </button>
  );
}
