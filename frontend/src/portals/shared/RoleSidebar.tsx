import { ChevronDown, ChevronRight, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import "./role-sidebar.css";

export type RoleSidebarIcon =
  | "overview"
  | "requests"
  | "people"
  | "review"
  | "schedule"
  | "capacity"
  | "messages"
  | "history"
  | "agent"
  | "queue"
  | "criteria"
  | "documents"
  | "archive"
  | "search"
  | "progress"
  | "team"
  | "supervisor";

export type RoleSidebarItem = {
  id: string;
  label: string;
  icon: ReactNode;
  section?: string;
  disabled?: boolean;
};

type Props = {
  ariaLabel: string;
  workspaceLabel: string;
  items: readonly RoleSidebarItem[];
  active: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onSelect: (id: string) => void;
  onToggle: () => void;
  onClose: () => void;
  className?: string;
  expandedSections?: Readonly<Record<string, boolean>>;
  onToggleSection?: (section: string, open?: boolean) => void;
};

const paths: Record<RoleSidebarIcon, ReactNode> = {
  overview: <><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></>,
  requests: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 13h6m-6 4h4"/></>,
  people: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 8a3 3 0 1 1 0 6m1 2a5 5 0 0 1 3 4"/></>,
  review: <><path d="M5 4h14v17H5z"/><path d="m8 10 2 2 4-4m-6 7 2 2 4-4"/></>,
  schedule: <><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M8 3v4m8-4v4M4 10h16M8 14h3m-3 3h6"/></>,
  capacity: <><path d="M4 19h16M6 16v-3M12 16V8M18 16v-6"/><path d="m5 9 4-4 4 3 5-5"/></>,
  messages: <><path d="M4 5h16v12H8l-4 4V5Z"/><path d="M8 9h8M8 13h5"/></>,
  history: <><path d="M4 12a8 8 0 1 0 2.3-5.7"/><path d="M4 5v5h5M12 8v5l3 2"/></>,
  agent: <><circle cx="12" cy="12" r="7"/><path d="M12 2v3M12 19v3M2 12h3m14 0h3M9 12h6M12 9v6"/></>,
  queue: <><path d="M5 4h14v17H5z"/><path d="M8 9h8M8 13h6M8 17h4"/></>,
  criteria: <><path d="M4 5h16v14H4z"/><path d="M8 9h8M8 13h6M8 17h4"/></>,
  documents: <><path d="M6 3h8l4 4v14H6V3Z"/><path d="M14 3v5h5M9 13h6m-6 4h5"/></>,
  archive: <><path d="M4 7h16v13H4zM3 4h18v3H3zM9 11h6"/></>,
  search: <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/></>,
  progress: <><path d="M4 19V5m0 14h16"/><path d="m7 15 3-4 3 2 5-7"/></>,
  team: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 8a3 3 0 1 1 0 6m1 2a5 5 0 0 1 3 4"/></>,
  supervisor: <><circle cx="9" cy="8" r="3"/><path d="M3 20a6 6 0 0 1 12 0M17 14v6m-3-3h6"/></>,
};

export function SidebarIcon({ name }: { name: RoleSidebarIcon }) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

export function RoleSidebar({ ariaLabel, workspaceLabel, items, active, collapsed, mobileOpen, onSelect, onToggle, onClose, expandedSections, onToggleSection, className = "" }: Props) {
  const sections = [...new Set(items.map((item) => item.section ?? ""))];
  const activeSection = items.find((item) => item.id === active)?.section ?? sections[0] ?? "";
  const [selectedSection, setSelectedSection] = useState(activeSection);
  const [internalExpanded, setInternalExpanded] = useState<Record<string, boolean>>(() => Object.fromEntries(sections.map((section) => [section, section === activeSection])));
  const isSectionOpen = (section: string) => expandedSections?.[section] ?? internalExpanded[section] ?? true;
  const toggleSection = (section: string) => {
    const open = !isSectionOpen(section);
    if (onToggleSection) {
      onToggleSection(section, open);
      return;
    }
    setInternalExpanded(() => Object.fromEntries(sections.map((item) => [item, item === section ? open : false])));
  };
  const selectSection = (section: string) => {
    setSelectedSection(section);
    if (!isSectionOpen(section)) {
      if (onToggleSection) onToggleSection(section, true);
      else setInternalExpanded((current) => ({ ...current, [section]: true }));
    }
    if (collapsed) onToggle();
  };

  useEffect(() => {
    if (activeSection) setSelectedSection(activeSection);
  }, [active, activeSection]);

  useEffect(() => {
    if (onToggleSection) return;
    const activeItem = items.find((item) => item.id === active);
    const section = activeItem?.section ?? "";
    if (!section) return;
    setInternalExpanded((current) => (current[section] ? current : { ...current, [section]: true }));
  }, [active, items, onToggleSection]);

  const railSections = sections.filter(Boolean);

  return <>
    <aside className={`student-sidebar role-sidebar ${className} ${mobileOpen ? "student-sidebar--open" : ""} ${collapsed ? "student-sidebar--collapsed" : ""}`}>
      <button type="button" className="student-sidebar__collapse role-sidebar__collapse" aria-label={collapsed ? "Expand navigation" : "Collapse navigation"} aria-expanded={!collapsed} onClick={onToggle}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={collapsed ? "m9 6 6 6-6 6" : "m15 6-6 6 6 6"}/></svg>
      </button>
      <div className="role-sidebar__rail">
        <div className="role-sidebar__rail-list" aria-label={`${workspaceLabel} menu sections`}>
          {railSections.map((section) => {
            const firstItem = items.find((item) => item.section === section);
            const selected = selectedSection === section;
            return <button key={section} type="button" className="role-sidebar__rail-item" aria-label={`Open ${section}`} aria-pressed={selected} title={section} onClick={() => selectSection(section)}>
              <span className="role-sidebar__rail-icon" aria-hidden="true">{firstItem?.icon}</span>
            </button>;
          })}
        </div>
      </div>
      <div className="role-sidebar__panel">
        <div className="student-sidebar__mobile-head">
          <button type="button" className="student-sidebar__close" aria-label="Close navigation" onClick={onClose}><X strokeWidth={1.75} size={18} aria-hidden /></button>
        </div>
        <nav className="student-sidebar__nav" aria-label={ariaLabel}>
          <div className="role-sidebar__menu-list">
            {railSections.map((section) => {
              const sectionItems = items.filter((item) => item.section === section);
              const selected = selectedSection === section;
              const sectionOpen = selected && isSectionOpen(section);
              return <section className={`role-sidebar__menu-section ${selected ? "is-selected" : ""}`} key={section}>
                <button type="button" className="role-sidebar__menu-section-head" aria-expanded={sectionOpen} aria-label={`${sectionOpen ? "Collapse" : "Expand"} ${section}`} onClick={() => {
                  setSelectedSection(section);
                  if (selected) toggleSection(section);
                  else if (!isSectionOpen(section)) {
                    if (onToggleSection) onToggleSection(section, true);
                    else setInternalExpanded((current) => Object.fromEntries(sections.map((item) => [item, item === section])));
                  }
                }}>
                  <span className="role-sidebar__menu-section-name"><span className="role-sidebar__menu-section-icon" aria-hidden="true">{sectionItems[0]?.icon}</span><span>{section}</span></span>
                  {sectionOpen ? <ChevronDown strokeWidth={1.8} size={16} aria-hidden="true" /> : <ChevronRight strokeWidth={1.8} size={16} aria-hidden="true" />}
                </button>
                {sectionOpen && <div className="role-sidebar__section-items">{sectionItems.map((item) => <button key={item.id} type="button" className="student-sidebar__item" disabled={item.disabled} aria-current={active === item.id ? "page" : undefined} aria-label={item.label} title={collapsed ? item.label : undefined} onClick={() => { onSelect(item.id); onClose(); }}>
                    <span className="student-sidebar__icon" aria-hidden="true">{item.icon}</span>
                    <span className="student-sidebar__label">{item.label}</span>
                  </button>)}</div>}
              </section>;
            })}
          </div>
        </nav>
      </div>
    </aside>
    <button type="button" aria-label="Close navigation" className={`student-sidebar__overlay ${mobileOpen ? "student-sidebar__overlay--open" : ""}`} onClick={onClose}/>
  </>;
}
