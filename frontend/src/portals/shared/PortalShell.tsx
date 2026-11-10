import { useEffect, type ReactNode } from "react";
import "./portal-shell.css";

type Props = {
  roleLabel: string;
  userName: string;
  initials: string;
  collapsed: boolean;
  mobileOpen: boolean;
  onOpenMobile: () => void;
  onLogout: () => void;
  sidebar: ReactNode;
  children: ReactNode;
  className?: string;
};

export function PortalShell({ roleLabel, userName, initials, collapsed, mobileOpen, onOpenMobile, onLogout, sidebar, children, className = "" }: Props) {
  useEffect(() => {
    if (!mobileOpen || !window.matchMedia("(max-width: 767px)").matches) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, [mobileOpen]);

  return <main className={`portal-shell student-shell ${className}`} data-sidebar={collapsed ? "collapsed" : "expanded"} data-mobile-open={mobileOpen ? "true" : "false"}>
    <header className="portal-header">
      <div className="portal-header__left">
        <button type="button" className="portal-header__menu" aria-label="Open navigation" aria-expanded={mobileOpen} onClick={onOpenMobile}><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg></button>
      </div>
      <div className="portal-header__center">
        <div className="portal-brand"><svg aria-hidden="true" viewBox="0 0 56 40" fill="none"><path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor"/><path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><circle cx="49" cy="30" r="3" fill="#e4eee7" stroke="currentColor" strokeWidth="2"/></svg><span>FYPHub</span></div>
        <span className="portal-role">{roleLabel}</span>
      </div>
      <div className="portal-account"><span className="portal-avatar" aria-hidden="true">{initials}</span><span className="portal-account__name">{userName}</span><button type="button" className="portal-logout" onClick={onLogout}>Logout</button></div>
    </header>
    <div className="portal-body">
      {sidebar}
      <section className="portal-content"><div className="portal-content__inner">{children}</div></section>
    </div>
  </main>;
}
