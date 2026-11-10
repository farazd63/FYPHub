import { RoleSidebar, SidebarIcon, type RoleSidebarItem } from "../shared/RoleSidebar";
import type { ReactNode } from "react";

export type StudentPhase = { id: string; name: string; route: string; status: "Implemented" | "Partial"; icon: ReactNode };

type Props = {
  phases: readonly StudentPhase[];
  activeId: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onSelect: (phase: StudentPhase) => void;
  onOverview: () => void;
  onToggleCollapse: () => void;
  onCloseMobile: () => void;
};

const sectionFor = (id: string) => id === "overview" ? "Workspace" : id === "search" || id === "archive" ? "Knowledge & Archive" : "Project Journey";

export function StudentSidebar({ phases, activeId, collapsed, mobileOpen, onSelect, onOverview, onToggleCollapse, onCloseMobile }: Props) {
  const items: RoleSidebarItem[] = [
    { id: "overview", label: "Overview", icon: <SidebarIcon name="overview" />, section: "Workspace" },
    ...phases.map((phase) => ({ id: phase.id, label: phase.name, icon: phase.icon, section: sectionFor(phase.id) })),
  ];

  return <RoleSidebar
    ariaLabel="Student workspace navigation"
    workspaceLabel="Student workspace"
    items={items}
    active={activeId}
    collapsed={collapsed}
    mobileOpen={mobileOpen}
    onSelect={(id) => {
      if (id === "overview") {
        onOverview();
        return;
      }
      const phase = phases.find((item) => item.id === id);
      if (phase) onSelect(phase);
    }}
    onToggle={onToggleCollapse}
    onClose={onCloseMobile}
  />;
}
