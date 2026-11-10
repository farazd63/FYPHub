import type { EvaluatorNavKey } from "./EvaluatorPortal";
import { RoleSidebar, SidebarIcon, type RoleSidebarItem } from "../shared/RoleSidebar";

type Props = { active: EvaluatorNavKey; collapsed: boolean; mobileOpen: boolean; onSelect: (key: EvaluatorNavKey) => void; onToggle: () => void; onClose: () => void };

const items: readonly RoleSidebarItem[] = [
  { id: "overview", label: "Overview", icon: <SidebarIcon name="overview" />, section: "Workspace" },
  { id: "queue", label: "Evaluation Queue", icon: <SidebarIcon name="queue" />, section: "Evaluation" },
  { id: "proposal", label: "Proposal Review", icon: <SidebarIcon name="review" />, section: "Evaluation" },
  { id: "criteria", label: "Evaluation Criteria", icon: <SidebarIcon name="criteria" />, section: "Evaluation" },
  { id: "scoring", label: "Scoring & Feedback", icon: <SidebarIcon name="review" />, section: "Evaluation" },
  { id: "schedule", label: "Defense Schedule", icon: <SidebarIcon name="schedule" />, section: "Schedule & History" },
  { id: "history", label: "Decision History", icon: <SidebarIcon name="history" />, section: "Schedule & History" },
];

export function EvaluatorSidebar({ active, collapsed, mobileOpen, onSelect, onToggle, onClose }: Props) {
  return <RoleSidebar
    ariaLabel="Evaluator navigation"
    workspaceLabel="Evaluator workspace"
    items={items}
    active={active}
    collapsed={collapsed}
    mobileOpen={mobileOpen}
    onSelect={(key) => onSelect(key as EvaluatorNavKey)}
    onToggle={onToggle}
    onClose={onClose}
  />;
}
