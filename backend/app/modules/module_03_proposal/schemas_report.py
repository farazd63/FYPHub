from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class ProposalOut(BaseModel):
    proposal_id: str
    proposal_type: str
    document_id: str
    version: int
    extraction_status: str
    ast: dict[str, Any]
    extraction_warnings: list[Any]


class ReportOut(BaseModel):
    report_id: str
    proposal_id: str
    proposal_type: str
    report_version: int
    status: str
    check_1: dict[str, Any]
    check_2: dict[str, Any]
    check_3: dict[str, Any]
    total_findings: int
    severity_counts: dict[str, int]
    remediation: list[str]
    advisory_summary: str
    runtime_metadata: dict[str, Any]
    generated_at: datetime


class SeverityCounts(BaseModel):
    INFO: int = 0
    WARNING: int = 0
    ERROR: int = 0


class RuntimeMetadata(BaseModel):
    model_config = {"extra": "allow"}
    runtime: str
    model: str | None = None
    timestamp: str | None = None


class TierFinding(BaseModel):
    model_config = {"extra": "forbid"}
    severity: Literal["INFO", "WARNING", "ERROR"]
    rule_reference: str
    observed_value: Any = None
    expected_value: Any = None
    evidence: dict[str, Any] = {}
    remediation: str
    confidence: str = "UNKNOWN"


class DeepComplianceReport(BaseModel):
    model_config = {"extra": "forbid"}
    proposal_type: Literal["SHORT", "LONG"]
    proposal_id: str
    proposal_version: int
    baseline_template_id: str
    baseline_version: int
    extraction_status: str
    tier_1: list[TierFinding] = []
    tier_2: list[TierFinding] = []
    tier_3: list[TierFinding] = []
    severity_counts: SeverityCounts
    parser_warnings: list[Any] = []
    ai_availability: Literal["AVAILABLE", "UNAVAILABLE"]
    remediation: list[str] = []
    advisory_summary: str
    runtime_metadata: RuntimeMetadata
    status: Literal["PASS", "PASS_WITH_WARNINGS", "NEEDS_REVISION", "UNAVAILABLE"]
