import { RoleSidebar, SidebarIcon, type RoleSidebarItem } from "../shared/RoleSidebar";

export const coordinatorNav: readonly RoleSidebarItem[] = [
  { id: "registry", label: "FYP Students & Projects", icon: <SidebarIcon name="people" />, section: "Workspace" },
  { id: "requests", label: "Supervisor Requests", icon: <SidebarIcon name="requests" />, section: "People & Access" },
];

export function CoordinatorSidebar({ active, collapsed, mobileOpen, onSelect, onToggle, onClose }: { active: string; collapsed: boolean; mobileOpen: boolean; onSelect: (id: string) => void; onToggle: () => void; onClose: () => void }) {
  return <RoleSidebar ariaLabel="Coordinator navigation" workspaceLabel="Coordinator workspace" items={coordinatorNav} active={active} collapsed={collapsed} mobileOpen={mobileOpen} onSelect={onSelect} onToggle={onToggle} onClose={onClose} />;
}
