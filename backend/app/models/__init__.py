"""Application SQLAlchemy models."""

from .user import User, UserRole
from .academic import AcademicCycle, AcademicGroupPolicy, SupervisorCapacityPolicy
from .team import Team, TeamMember
from .auth_session import AuthSession
from .password_reset_token import PasswordResetToken
from .audit_event import AdminAuditEvent
from .template_reference import TemplateReference, TemplateReferenceVersion, AcademicRuleVersion, TemplateType
from .evaluation_rubric import EvaluationRubric, EvaluationRubricVersion, EvaluationRubricCriterion
from .academic_deadline import AcademicDeadline, AcademicDeadlineVersion

__all__ = ["User", "UserRole", "AcademicCycle", "AcademicGroupPolicy", "SupervisorCapacityPolicy", "Team", "TeamMember", "AuthSession", "PasswordResetToken", "AdminAuditEvent", "TemplateReference", "TemplateReferenceVersion", "AcademicRuleVersion", "TemplateType", "EvaluationRubric", "EvaluationRubricVersion", "EvaluationRubricCriterion", "AcademicDeadline", "AcademicDeadlineVersion"]

from .reminder_rule import ReminderRule, ReminderRuleVersion

from .student_roster import ApprovedStudent, RosterImport

from .workflow_policy import WorkflowPolicy, WorkflowPolicyVersion

from .supervisor_assignment import SupervisorAssignment

from .group_message import GroupMessage

from .team_preference import TeamPreference

from .match_chat import MatchChat, MatchMessage, MatchConsent

from .individual_verification import IdentityChallenge, IdentityProof

from .anonymous_verification import AnonymousVerificationContext, AnonymousVerificationChallenge, AnonymousIdentityProof

from .join_request import JoinRequest, JoinRequestAudit

from .invitation import Invitation, InvitationAudit

from .invitation import InvitationOutbox

from .supervisor_request import SupervisorRequest, SupervisorRequestDocument, SupervisorRequestExtractionStatus, SupervisorRequestStatus, SupervisorRequestStatusHistory, SupervisorRequestSubmissionNoteVersion
from .proposal import Proposal, ProposalVersion
from .proposal_reference import ProposalReference, ProposalReferenceDocument
from .supervisor_request_conversation import SupervisorRequestMessage
from .fyp_registry import FypRegistryMetadata
from .archived_project import ArchivedProject, ArchivedProjectDocument, ArchivedProjectDocumentType
from ..modules.module_03_proposal.models import M03CheckRun, M03ComplianceFinding, M03ComplianceReport, M03ExtractionStatus, M03ProposalDocument, M03ProposalType, M03ReferenceTemplate, M03ReportStatus, M03Severity, M03TemplateRule
from .project_workflow import ProjectMilestone, ProjectTask, SupervisionMeeting, DefenseSchedule, DefensePanelMember, PanelEvaluation, PanelEvaluationScore
from .agent_supervision import SupervisionAgentRun
