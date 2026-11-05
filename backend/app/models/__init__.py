"""Application SQLAlchemy models."""

from .user import User, UserRole
from .academic import AcademicCycle, AcademicGroupPolicy, SupervisorCapacityPolicy
from .team import Team, TeamMember
from .auth_session import AuthSession
from .password_reset_token import PasswordResetToken
from .audit_event import AdminAuditEvent
from .template_reference import TemplateReference, TemplateReferenceVersion, AcademicRuleVersion, TemplateType
from .evaluation_rubric import EvaluationRubric, EvaluationRubricVersion, EvaluationRubricCriterion
from .evaluation import EvaluationRecord, EvaluationAuditEvent, EvaluationCorrection, EvaluationAggregationConfig
from .dashboard_requirement import DashboardRequirement
from .academic_deadline import AcademicDeadline, AcademicDeadlineVersion
from .document_requirement import DocumentUploadRequirement, DocumentSubmission, DocumentSubmissionVersion

__all__ = ["User", "UserRole", "AcademicCycle", "AcademicGroupPolicy", "SupervisorCapacityPolicy", "Team", "TeamMember", "AuthSession", "PasswordResetToken", "AdminAuditEvent", "TemplateReference", "TemplateReferenceVersion", "AcademicRuleVersion", "TemplateType", "EvaluationRubric", "EvaluationRubricVersion", "EvaluationRubricCriterion", "EvaluationRecord", "EvaluationAuditEvent", "EvaluationCorrection", "EvaluationAggregationConfig", "AcademicDeadline", "AcademicDeadlineVersion", "DashboardRequirement", "DocumentUploadRequirement", "DocumentSubmission", "DocumentSubmissionVersion"]

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
from .proposal_ai_review import ProposalAIReviewRun
from .proposal_reference import ProposalReference, ProposalReferenceDocument
from .proposal_compliance import ProposalComplianceSubmission, ProposalComplianceReport
from .supervisor_request_conversation import SupervisorRequestMessage
from .fyp_registry import FypRegistryMetadata
from .archived_project import ArchivedProject, ArchivedProjectDocument, ArchivedProjectDocumentType
from .project_workflow import ProjectMilestone, ProjectTask, SupervisionMeeting, DefenseSchedule, DefensePanelMember, PanelEvaluation, PanelEvaluationScore
from .module2_collaboration import Module2Notification, Module2ChannelRead, Module2MatchReport, Module2ChatbotSession
from .agent_supervision import SupervisionAgentRun
