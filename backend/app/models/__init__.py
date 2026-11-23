"""Application SQLAlchemy models."""

from .user import User, UserRole
from .institution import Institution, InstitutionDomain, InstitutionMembership, InstitutionInvitation, EmailVerificationToken
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
from .document_requirement import DocumentArchiveReviewQueue, DocumentRequirementSection, DocumentSubmission, DocumentSubmissionReviewEvent, DocumentSubmissionVersion, DocumentUploadRequirement

__all__ = ["User", "UserRole", "Institution", "InstitutionDomain", "InstitutionMembership", "InstitutionInvitation", "EmailVerificationToken", "AcademicCycle", "AcademicGroupPolicy", "SupervisorCapacityPolicy", "Team", "TeamMember", "AuthSession", "PasswordResetToken", "AdminAuditEvent", "TemplateReference", "TemplateReferenceVersion", "AcademicRuleVersion", "TemplateType", "EvaluationRubric", "EvaluationRubricVersion", "EvaluationRubricCriterion", "EvaluationRecord", "EvaluationAuditEvent", "EvaluationCorrection", "EvaluationAggregationConfig", "AcademicDeadline", "AcademicDeadlineVersion", "DashboardRequirement", "DocumentUploadRequirement", "DocumentSubmission", "DocumentSubmissionVersion", "DocumentRequirementSection", "DocumentSubmissionReviewEvent", "DocumentArchiveReviewQueue", "ArchivedProject", "ArchivedProjectDocument", "ArchivedProjectDocumentType", "ArchiveImportBatch", "ProposalComplianceSubmission", "ProposalComplianceReport", "ProposalVersionComparison"]

from .reminder_rule import ReminderRule, ReminderRuleVersion

from .supervisor_assignment import SupervisorAssignment
from .supervisor_replacement import SupervisorDeparture, SupervisorReplacementCase
__all__.extend(["SupervisorDeparture", "SupervisorReplacementCase"])

from .group_message import GroupMessage
from .group_ai import GroupAIDocumentChunk, GroupAIResponse
from .student_ai import StudentAIConversation, StudentAIMessage
__all__.extend(["GroupMessage", "GroupAIDocumentChunk", "GroupAIResponse", "StudentAIConversation", "StudentAIMessage"])
from .announcement import Announcement, AnnouncementRead
__all__.extend(["Announcement", "AnnouncementRead"])

from .supervisor_request import SupervisorRequest, SupervisorRequestDocument, SupervisorRequestExtractionStatus, SupervisorRequestStatus, SupervisorRequestStatusHistory, SupervisorRequestSubmissionNoteVersion
from .proposal import Proposal, ProposalVersion
from .proposal_ai_review import ProposalAIReviewRun
from .proposal_reference import ProposalReference, ProposalReferenceDocument
from .proposal_compliance import ProposalComplianceSubmission, ProposalComplianceReport, ProposalVersionComparison
from .supervisor_request_conversation import SupervisorRequestMessage
from .archived_project import ArchivedProject, ArchivedProjectDocument, ArchivedProjectDocumentType
from .archive_import_batch import ArchiveImportBatch
from .project_workflow import ProjectMilestone, ProjectTask, SupervisionMeeting, DefenseSchedule, DefensePanelMember, PanelEvaluation, PanelEvaluationScore
from .module2_collaboration import (
    Module2Notification,
    Module2ChannelRead,
    Module2ChatbotSession,
    CollaborationChannel,
    CollaborationParticipant,
    CollaborationMessage,
    CollaborationMemberCredential,
    CollaborationMemberSession,
    CollaborationPasswordResetRequest,
)
from .agent_supervision import SupervisionAgentRun
from .supervisor_matching import (
    MatchingAuditLog,
    MatchingConfiguration,
    KnowledgeDocument,
    KnowledgeDocumentChunk,
    ProfileVerificationRecord,
    ProposalAnalysis,
    ProposalAnalysisVersion,
    SupervisedProjectHistory,
    SupervisorAvailability,
    SupervisorDocument,
    SupervisorExpertise,
    SupervisorMatchResult,
    SupervisorProfile,
    SupervisorResearchInterest,
    SupervisorSkill,
)
__all__.extend([
    "SupervisorProfile", "SupervisorExpertise", "SupervisorSkill", "SupervisorResearchInterest",
    "SupervisorDocument", "SupervisedProjectHistory", "SupervisorAvailability", "ProposalAnalysis",
    "ProposalAnalysisVersion", "SupervisorMatchResult", "MatchingConfiguration", "ProfileVerificationRecord",
    "MatchingAuditLog", "KnowledgeDocument", "KnowledgeDocumentChunk",
])
