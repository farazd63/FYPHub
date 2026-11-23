import { Home } from "lucide-react";
import { appPath, appPathname } from "../../platform-path";

type Props = {
  onClick?: () => void;
  className?: string;
};

function defaultHome() {
  const path = appPathname();
  const homePath = path.startsWith("/admin") ? "/admin" : path.startsWith("/student") ? "/student" : path.startsWith("/supervisor") ? "/supervisor" : path.startsWith("/coordinator") ? "/coordinator" : path.startsWith("/evaluator") ? "/evaluator" : path;
  window.location.assign(appPath(homePath));
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
