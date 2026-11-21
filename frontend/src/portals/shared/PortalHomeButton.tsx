import { Home } from "lucide-react";

type Props = {
  onClick?: () => void;
  className?: string;
};

function defaultHome() {
  const path = window.location.pathname;
  const homePath = path.startsWith("/admin") ? "/admin" : path.startsWith("/student") ? "/student" : path.startsWith("/supervisor") ? "/supervisor" : path.startsWith("/coordinator") ? "/coordinator" : path.startsWith("/evaluator") ? "/evaluator" : path;
  window.location.assign(homePath);
}

export function PortalHomeButton({ onClick = defaultHome, className = "" }: Props) {
  return (
    <button
      type="button"
      className={`portal-home-button ${className}`}
      aria-label="Go to overview"
      title="Go to overview"
      onClick={onClick}
    >
      <Home size={16} strokeWidth={1.9} aria-hidden="true" />
    </button>
  );
}
