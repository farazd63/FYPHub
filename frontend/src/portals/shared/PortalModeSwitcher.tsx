import "./portal-mode-switcher.css";

export type PortalMode = "SUPERVISOR" | "COORDINATOR" | "PANEL_MEMBER" | "ADMIN";

type Props = {
  active: PortalMode;
  available: PortalMode[];
  onChange: (mode: PortalMode) => void;
};

const labels: Record<PortalMode, string> = {
  SUPERVISOR: "Supervisor",
  COORDINATOR: "Coordinator",
  PANEL_MEMBER: "Evaluator",
  ADMIN: "Administrator",
};

export function PortalModeSwitcher({ active, available, onChange }: Props) {
  return (
    <div className="portal-mode-switcher" role="group" aria-label="Portal">
      {available.map((mode) => <button key={mode} type="button" className={active === mode ? "is-active" : ""} aria-pressed={active === mode} onClick={() => onChange(mode)}>{labels[mode]}</button>)}
    </div>
  );
}
