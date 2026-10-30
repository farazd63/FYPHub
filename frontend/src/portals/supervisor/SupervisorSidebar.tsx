type NavItem = { id: string; label: string; icon: string };

export const supervisorNav: NavItem[] = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "requests", label: "Supervisor Requests", icon: "▣" },
  { id: "assigned", label: "Assigned Students & Teams", icon: "◎" },
  { id: "review", label: "Proposal Review", icon: "✓" },
  { id: "capacity", label: "Supervisor Capacity", icon: "▥" },
  { id: "conversations", label: "Conversations", icon: "☷" },
  { id: "history", label: "Decision History", icon: "◷" },
];

export function SupervisorSidebar({
  active,
  collapsed,
  mobileOpen,
  onSelect,
  onToggle,
  onClose,
}: {
  active: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onSelect: (id: string) => void;
  onToggle: () => void;
  onClose: () => void;
}) {
  return <>
    <aside className={`student-sidebar ${mobileOpen ? "student-sidebar--open" : ""} ${collapsed ? "student-sidebar--collapsed" : ""}`}>
      <div className="student-sidebar__mobile-head"><span className="student-sidebar__section-label">Supervisor workspace</span><button type="button" className="student-sidebar__close" aria-label="Close navigation" onClick={onClose}>×</button></div>
      <button type="button" className="student-sidebar__collapse" aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-expanded={!collapsed} onClick={onToggle}><span aria-hidden="true">{collapsed ? "›" : "‹"}</span></button>
      <nav className="student-sidebar__nav" aria-label="Supervisor navigation">
        {supervisorNav.map((item) => <button type="button" key={item.id} aria-current={active === item.id ? "page" : undefined} className={`student-sidebar__item ${active === item.id ? "student-sidebar__item--active" : ""}`} onClick={() => { onSelect(item.id); onClose(); }}><span className="student-sidebar__icon" aria-hidden="true">{item.icon}</span><span className="student-sidebar__label">{item.label}</span></button>)}
      </nav>
    </aside>
    <button type="button" aria-label="Close navigation" className={`student-sidebar__overlay ${mobileOpen ? "student-sidebar__overlay--open" : ""}`} onClick={onClose} />
  </>;
}
