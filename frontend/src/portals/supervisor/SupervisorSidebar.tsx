import { RoleSidebar, SidebarIcon, type RoleSidebarItem } from "../shared/RoleSidebar";

export const supervisorNav: readonly RoleSidebarItem[] = [
  { id: "overview", label: "Overview", icon: <SidebarIcon name="overview" />, section: "Workspace" },
  { id: "requests", label: "Supervisor Requests", icon: <SidebarIcon name="requests" />, section: "Requests & Review" },
  { id: "assigned", label: "Assigned Students & Teams", icon: <SidebarIcon name="people" />, section: "Supervision" },
  { id: "capacity", label: "Supervisor Capacity", icon: <SidebarIcon name="capacity" />, section: "Supervision" },
  { id: "history", label: "Decision History", icon: <SidebarIcon name="history" />, section: "History & Communication" },
];

export function SupervisorSidebar({ active, collapsed, mobileOpen, onSelect, onToggle, onClose }: { active: string; collapsed: boolean; mobileOpen: boolean; onSelect: (id: string) => void; onToggle: () => void; onClose: () => void }) {
  return <RoleSidebar
    ariaLabel="Supervisor navigation"
    workspaceLabel="Supervisor workspace"
    items={supervisorNav}
    active={active}
    collapsed={collapsed}
    mobileOpen={mobileOpen}
    onSelect={onSelect}
    onToggle={onToggle}
    onClose={onClose}
  />;
}
