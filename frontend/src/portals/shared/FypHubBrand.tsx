import { PortalHomeButton } from "./PortalHomeButton";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { ReactNode } from "react";

type FypHubBrandProps = { className?: string; afterHome?: ReactNode };

export function FypHubBrand({ className = "", afterHome }: FypHubBrandProps) {
  return <div className={`fyp-hub-brand ${className}`.trim()} aria-label="FYPHub">
    <PortalHomeButton />
    {afterHome ?? <div className="portal-history-controls" aria-label="Browser page navigation">
      <button type="button" aria-label="Go back" title="Go back" onClick={() => window.history.back()}>
        <ChevronLeft aria-hidden="true" size={15} strokeWidth={2} />
      </button>
      <button type="button" aria-label="Go forward" title="Go forward" onClick={() => window.history.forward()}>
        <ChevronRight aria-hidden="true" size={15} strokeWidth={2} />
      </button>
    </div>}
    <svg aria-hidden="true" viewBox="0 0 56 40" fill="none">
      <path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor" />
      <path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </svg>
    <span>FYPHub</span>
  </div>;
}
