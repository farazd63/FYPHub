import { useState } from "react";
import {
  BookOpen,
  ClipboardCheck,
  FileUp,
  GraduationCap,
  Menu,
  Presentation,
  ShieldCheck,
  TrendingUp,
  UserCheck,
  Users,
  UsersRound,
  X,
} from "lucide-react";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { Container } from "../ui/Container";
import { FeatureChip } from "../ui/FeatureChip";
import { Link } from "../ui/Link";
import { Section } from "../ui/Section";
import { ThemeToggle } from "../ui/ThemeToggle";
import "./welcome-landing.css";

type WelcomeLandingProps = {
  onLogin: () => void;
  onSignup: () => void;
};

const WORKFLOW_STEPS = [
  { id: "group", label: "Form group", icon: UsersRound },
  { id: "supervisor", label: "Choose supervisor", icon: UserCheck },
  { id: "proposal", label: "Submit proposal", icon: FileUp },
  { id: "compliance", label: "Compliance check", icon: ShieldCheck },
  { id: "progress", label: "Track progress", icon: TrendingUp },
  { id: "defence", label: "Defence", icon: Presentation },
] as const;

const ROLE_CARDS = [
  {
    title: "Student",
    description: "Group workspace for documents, proposals, and supervision.",
    icon: GraduationCap,
    bullets: [
      "Overview & group members",
      "Required documents & uploads",
      "Proposal compliance check",
      "Supervisor selection & requests",
      "Project progress dashboard",
      "FYP archive & knowledge search",
    ],
  },
  {
    title: "Supervisor",
    description: "Review requests and guide assigned student teams.",
    icon: UserCheck,
    bullets: [
      "Workspace overview",
      "Supervisor requests",
      "Assigned students & teams",
      "Supervisor capacity",
      "Decision history",
    ],
  },
  {
    title: "Coordinator",
    description: "Coordinate people access and panel scheduling.",
    icon: Users,
    bullets: ["Supervisor requests", "Panel scheduling"],
  },
  {
    title: "Panel Member",
    description: "Evaluator workspace for defence and scoring workflows.",
    icon: ClipboardCheck,
    bullets: [
      "Overview",
      "Evaluation queue",
      "Proposal review",
      "Evaluation criteria",
      "Scoring & feedback",
      "Defense schedule",
      "Decision history",
    ],
  },
  {
    title: "Admin",
    description: "Configure academic cycles first, then people, templates, and requirements.",
    icon: BookOpen,
    bullets: [
      "Overview & FYP archive",
      "Student groups & users & roles",
      "Academic cycles & policies",
      "Proposal templates",
      "Supervisor capacity",
      "Required documents",
    ],
  },
] as const;

function BrandMark() {
  return (
    <>
      <svg aria-hidden className="welcome-landing__nav-icon" viewBox="0 0 56 40" fill="none">
        <path d="m4 14 24-10 24 10-24 10L4 14Z" fill="currentColor" />
        <path d="M15 20v8c5 5 21 5 26 0v-8M49 16v11" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        <circle cx="49" cy="30" r="3" fill="currentColor" stroke="currentColor" strokeWidth="2" />
      </svg>
      <span>FYPHub</span>
    </>
  );
}

export function WelcomeLanding({ onLogin, onSignup }: WelcomeLandingProps) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="welcome-landing">
      <div className="welcome-landing__pattern" aria-hidden="true" />
      <header className="welcome-landing__nav-wrap">
        <nav className="welcome-landing__nav" aria-label="Primary">
          <a href="#overview" className="welcome-landing__nav-brand">
            <BrandMark />
          </a>
          <div className="welcome-landing__nav-links">
            <a href="#overview">Overview</a>
            <a href="#roles">Roles</a>
            <a href="#workflow">Workflow</a>
          </div>
          <div className="welcome-landing__nav-actions">
            <Button variant="secondary" size="sm" onClick={onLogin}>
              Login
            </Button>
            <Button size="sm" onClick={onSignup}>
              Get Started
            </Button>
            <ThemeToggle />
          </div>
          <button
            type="button"
            className="welcome-landing__menu-btn fy-icon-btn fy-icon-btn--md fy-icon-btn--secondary"
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            {menuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </nav>
        {menuOpen && (
          <div className="welcome-landing__mobile-menu">
            <a href="#overview" onClick={() => setMenuOpen(false)}>
              Overview
            </a>
            <a href="#roles" onClick={() => setMenuOpen(false)}>
              Roles
            </a>
            <a href="#workflow" onClick={() => setMenuOpen(false)}>
              Workflow
            </a>
            <Button variant="secondary" size="sm" onClick={() => { setMenuOpen(false); onLogin(); }}>
              Login
            </Button>
            <Button size="sm" onClick={() => { setMenuOpen(false); onSignup(); }}>
              Get Started
            </Button>
            <ThemeToggle />
          </div>
        )}
      </header>

      <main>
        <Container>
          <section id="overview" className="welcome-landing__hero">
            <p className="welcome-landing__eyebrow">Final Year Project Workspace</p>
            <h1>Manage Your Final Year Project with Intelligence</h1>
            <p className="welcome-landing__tagline">
              One guided workspace from group signup through final defence.
            </p>
            <p className="welcome-landing__lede">
              FYPHub keeps students, supervisors, coordinators, panel members, and administrators aligned on the same academic cycle, documents, and review steps — without scattered spreadsheets.
            </p>
            <div className="welcome-landing__cta-row">
              <Button size="lg" onClick={onSignup}>
                Get Started
              </Button>
              <Button variant="secondary" size="lg" onClick={onLogin}>
                Sign in
              </Button>
            </div>
            <div className="welcome-landing__chips">
              <FeatureChip icon={Users} active>
                Group workspace & collaboration
              </FeatureChip>
              <FeatureChip icon={ShieldCheck}>
                Proposal compliance workspace
              </FeatureChip>
              <FeatureChip icon={BookOpen}>
                FYP archive & knowledge search
              </FeatureChip>
            </div>
          </section>

          <Section
            id="workflow"
            title="Project workflow"
            description="Six connected stages every group moves through in FYPHub."
          >
            <h3 className="fy-sr-only">Workflow diagram</h3>
            <div className="welcome-landing__diagram">
              <ol className="welcome-landing__flow">
                {WORKFLOW_STEPS.map((step) => {
                  const Icon = step.icon;
                  return (
                    <li key={step.id} className="welcome-landing__flow-step">
                      <span className="welcome-landing__flow-icon">
                        <Icon size={18} strokeWidth={1.75} aria-hidden />
                      </span>
                      <span>{step.label}</span>
                    </li>
                  );
                })}
              </ol>
            </div>
          </Section>

          <Section
            id="roles"
            title="Choose your role"
            description="Each workspace mirrors the real sidebar menus inside FYPHub."
          >
            <div className="welcome-landing__roles">
              {ROLE_CARDS.map((role) => {
                const Icon = role.icon;
                return (
                  <Card key={role.title} padding="md" className="welcome-landing__role-card">
                    <div className="fy-role-card__head">
                      <span className="fy-role-card__icon" aria-hidden>
                        <Icon size={22} strokeWidth={1.75} />
                      </span>
                      <h3 className="fy-role-card__title">{role.title}</h3>
                    </div>
                    <p className="fy-role-card__desc">{role.description}</p>
                    <ul className="welcome-landing__role-menu">
                      {role.bullets.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                    <Link href="/login" className="fy-role-card__link" onClick={(event) => { event.preventDefault(); onLogin(); }}>
                      Sign in to {role.title.toLowerCase()} workspace
                    </Link>
                  </Card>
                );
              })}
            </div>
          </Section>

          <Section title="How it works" description="The same six steps as concise cards.">
            <div className="welcome-landing__how-grid">
              {WORKFLOW_STEPS.map((step) => (
                <Card key={step.id} padding="md" className="welcome-landing__how-card">
                  <h3>{step.label}</h3>
                  <p>
                    {step.id === "group" && "Register your academic cycle and create the shared group account."}
                    {step.id === "supervisor" && "Browse supervisors, send proposal requests, and track decisions."}
                    {step.id === "proposal" && "Upload proposal documents against your cycle requirements."}
                    {step.id === "compliance" && "Run compliance checks against the active template rules."}
                    {step.id === "progress" && "Monitor supervision milestones and required submissions."}
                    {step.id === "defence" && "Panel members schedule, review, and record defence outcomes."}
                  </p>
                </Card>
              ))}
            </div>
          </Section>

          <section className="welcome-landing__cta-band" aria-labelledby="welcome-cta-heading">
            <h2 id="welcome-cta-heading" className="fy-title">
              Ready to open your final year workspace?
            </h2>
            <p className="welcome-landing__lede welcome-landing__lede--center">
              Create your student group account or sign in with an existing role.
            </p>
            <div className="welcome-landing__cta-row welcome-landing__cta-row--center">
              <Button size="lg" onClick={onSignup}>
                Get Started
              </Button>
            </div>
          </section>
        </Container>
      </main>

      <footer className="welcome-landing__footer">
        <Container>
          <div className="welcome-landing__footer-grid">
            <div>
              <h3>Product</h3>
              <ul>
                <li>
                  <a href="#overview">Overview</a>
                </li>
                <li>
                  <Link href="/signup" onClick={(event) => { event.preventDefault(); onSignup(); }}>
                    Create group account
                  </Link>
                </li>
                <li>
                  <Link href="/login" onClick={(event) => { event.preventDefault(); onLogin(); }}>
                    Sign in
                  </Link>
                </li>
              </ul>
            </div>
            <div>
              <h3>Roles</h3>
              <ul>
                <li><a href="#roles">Student</a></li>
                <li><a href="#roles">Supervisor</a></li>
                <li><a href="#roles">Coordinator</a></li>
                <li><a href="#roles">Panel member</a></li>
                <li><a href="#roles">Admin</a></li>
              </ul>
            </div>
            <div>
              <h3>Workflow</h3>
              <ul>
                {WORKFLOW_STEPS.map((step) => (
                  <li key={step.id}>
                    <a href="#workflow">{step.label}</a>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <p className="welcome-landing__footer-note">FYPHub — Final year project workspace</p>
        </Container>
      </footer>
    </div>
  );
}