type Props = { name: string; role: string };

export function SidebarProfile({ name, role }: Props) {
  const initials = name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "U";
  return <div className="floating-sidebar__profile" aria-label={`${role} profile`}>
    <span className="floating-sidebar__avatar" aria-hidden="true">{initials}</span>
    <span className="floating-sidebar__identity"><strong>{name}</strong><small>{role}</small></span>
  </div>;
}
