import { RoleSidebar, SidebarIcon, type RoleSidebarItem } from "./RoleSidebar";

type AdminNavGroup = { id: string; label: string; items: readonly { label: string; page: string }[] };
type Props = { groups: readonly AdminNavGroup[]; active: string; collapsed: boolean; mobileOpen: boolean; permitted: boolean; expanded: Readonly<Record<string, boolean>>; onSelect: (page: string) => void; onToggle: () => void; onClose: () => void; onToggleSection: (section: string) => void };

function iconFor(page: string) {
  if (page === "overview") return <SidebarIcon name="overview" />;
  if (page === "users" || page === "eligibility" || page === "registry") return <SidebarIcon name="people" />;
  if (page === "cycles" || page === "schedule") return <SidebarIcon name="schedule" />;
  if (page === "templates" || page === "documentRequirements") return <SidebarIcon name="documents" />;
  if (page === "capacity") return <SidebarIcon name="capacity" />;
  if (page === "supervisorRequests") return <SidebarIcon name="requests" />;
  if (page === "workflow" || page === "rubrics" || page === "deadlines" || page === "reminders") return <SidebarIcon name="criteria" />;
  if (page === "archive") return <SidebarIcon name="archive" />;
  return <SidebarIcon name="history" />;
}

export function AdminSidebar({ groups, active, collapsed, mobileOpen, permitted, expanded, onSelect, onToggle, onClose, onToggleSection }: Props) {
  const items: RoleSidebarItem[] = groups.flatMap((group) => group.items.map((item) => ({ id: item.page, label: item.label, icon: iconFor(item.page), section: group.label, disabled: item.page === "documentRequirements" && !permitted })));
  const expandedByLabel = Object.fromEntries(groups.map((group) => [group.label, expanded[group.id] ?? true]));
  return <RoleSidebar ariaLabel="Admin navigation" workspaceLabel="Administrator workspace" items={items} active={active} collapsed={collapsed} mobileOpen={mobileOpen} expandedSections={expandedByLabel} onSelect={onSelect} onToggle={onToggle} onClose={onClose} onToggleSection={onToggleSection} className="admin-sidebar" />;
}
