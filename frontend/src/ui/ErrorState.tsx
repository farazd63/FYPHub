import { RefreshCw, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "./Button";

type ErrorStateProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
  action?: ReactNode;
  className?: string;
};

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
  action,
  className,
}: ErrorStateProps) {
  return (
    <div
      className={["fy-error-state", className].filter(Boolean).join(" ")}
      role="alert"
    >
      <WifiOff className="fy-error-state__icon" strokeWidth={1.75} size={28} aria-hidden />
      <h3 className="fy-error-state__title">{title}</h3>
      <p className="fy-error-state__message">{message}</p>
      <div className="fy-error-state__actions">
        {onRetry && (
          <Button variant="secondary" onClick={onRetry}>
            <RefreshCw strokeWidth={1.75} size={16} aria-hidden />
            Try again
          </Button>
        )}
        {action}
      </div>
    </div>
  );
}