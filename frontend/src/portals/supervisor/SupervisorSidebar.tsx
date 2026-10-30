type NavItem = { id: string; label: string; icon: string };

export const supervisorNav: NavItem[] = [
  { id: "overview", label: "Overview", icon: "O" },
  { id: "requests", label: "Supervisor Requests", icon: "R" },
  { id: "assigned", label: "Assigned Students & Teams", icon: "T" },
  { id: "review", label: "Proposal Review", icon: "P" },
  { id: "capacity", label: "Supervisor Capacity", icon: "C" },
  { id: "conversations", label: "Conversations", icon: "M" },
  { id: "history", label: "Decision History", icon: "H" },
  { id: "agent-supervision", label: "Agentic Supervision", icon: "AI" },
];

export function SupervisorSidebar({ active, collapsed, mobileOpen, onSelect, onToggle, onClose }: { active: string; collapsed: boolean; mobileOpen: boolean; onSelect: (id: string) => void; onToggle: () => void; onClose: () => void }) {
  const toggleLabel = collapsed ? "Expand navigation" : "Collapse navigation";
  return <><aside className={`student-sidebar ${mobileOpen ? "student-sidebar--open" : ""} ${collapsed ? "student-sidebar--collapsed" : ""}`}><button type="button" aria-label={toggleLabel} className="student-sidebar__collapse" onClick={onToggle}>Toggle</button><nav aria-label="Supervisor navigation">{supervisorNav.map((item) => <button type="button" key={item.id} aria-current={active === item.id ? "page" : undefined} onClick={() => { onSelect(item.id); onClose(); }}>{item.icon} {item.label}</button>)}</nav></aside><button type="button" aria-label="Close navigation" className={`student-sidebar__overlay ${mobileOpen ? "student-sidebar__overlay--open" : ""}`} onClick={onClose} /></>;
}
