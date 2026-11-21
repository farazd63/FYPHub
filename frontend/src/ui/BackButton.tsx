import { ArrowLeft } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type BackButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
};

export function BackButton({ children, className, type = "button", ...rest }: BackButtonProps) {
  return <button type={type} className={["fy-back-button", className].filter(Boolean).join(" ")} {...rest}>
    <ArrowLeft className="fy-back-button__icon" size={17} strokeWidth={2} aria-hidden="true" />
    <span>{children}</span>
  </button>;
}
