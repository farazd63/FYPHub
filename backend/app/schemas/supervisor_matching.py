"""Validated request/response contracts for supervisor matching."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    evidence: str = Field(default="", max_length=1000)
    confidence: float = Field(default=1, ge=0, le=1)
    verified: bool = False


class ProposalExtraction(BaseModel):
    """The only fields the proposal matching model is allowed to return."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=255)
    topic: str = Field(default="", max_length=1000)
    problem_statement: str = Field(default="", max_length=4000)
    objectives: list[str] = Field(default_factory=list, max_length=12)
    methodology: str = Field(default="", max_length=3000)
    proposed_solution: str = Field(default="", max_length=3000)
    scope: str = Field(default="", max_length=3000)
    expected_outcomes: list[str] = Field(default_factory=list, max_length=12)
    research_domain: list[str] = Field(default_factory=list, max_length=12)
    required_skills: list[str] = Field(default_factory=list, max_length=20)
    technologies: list[str] = Field(default_factory=list, max_length=20)
    methods: list[str] = Field(default_factory=list, max_length=20)
    keywords: list[str] = Field(default_factory=list, max_length=30)
    confidence: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)

    @field_validator("objectives", "expected_outcomes", "research_domain", "required_skills", "technologies", "methods", "keywords")
    @classmethod
    def clean_lists(cls, value: list[str]) -> list[str]:
        return [item.strip()[:255] for item in value if item and item.strip()]


class ProfileExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    biography: str = Field(default="", max_length=5000)
    degree: str = Field(default="", max_length=255)
    specialization: str = Field(default="", max_length=255)
    expertise: list[EvidenceItem] = Field(default_factory=list, max_length=40)
    skills: list[EvidenceItem] = Field(default_factory=list, max_length=60)
    research_interests: list[EvidenceItem] = Field(default_factory=list, max_length=40)
    publications: list[EvidenceItem] = Field(default_factory=list, max_length=60)
    preferred_categories: list[str] = Field(default_factory=list, max_length=20)
    confidence: dict[str, float] = Field(default_factory=dict)
    evidence: dict[str, str] = Field(default_factory=dict)


class ProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    department: str | None = Field(default=None, max_length=255)
    program: str | None = Field(default=None, max_length=255)
    designation: str | None = Field(default=None, max_length=255)
    biography: str | None = Field(default=None, max_length=5000)
    degree: str | None = Field(default=None, max_length=255)
    specialization: str | None = Field(default=None, max_length=255)
    preferred_categories: list[str] = Field(default_factory=list, max_length=20)
    expertise: list[EvidenceItem] = Field(default_factory=list, max_length=40)
    skills: list[EvidenceItem] = Field(default_factory=list, max_length=60)
    research_interests: list[EvidenceItem] = Field(default_factory=list, max_length=40)
    publications: list[EvidenceItem] = Field(default_factory=list, max_length=60)


class AvailabilityWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    available: bool = True
    maximum_capacity: int = Field(default=0, ge=0, le=1000)


class MatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_cycle_id: int | None = Field(default=None, gt=0)
    limit: int = Field(default=10, ge=1, le=50)


class SupervisorRequestFromMatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(default="", max_length=2000)


class VerificationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["VERIFIED", "REJECTED", "ARCHIVED"]
    comment: str | None = Field(default=None, max_length=2000)


class MatchingConfigWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    academic_cycle_id: int | None = Field(default=None, gt=0)
    weights: dict[str, float]
    eligibility_rules: dict[str, object] = Field(default_factory=dict)
    algorithm_version: str = Field(default="supervisor-matching-v1", min_length=1, max_length=64)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, value: dict[str, float]) -> dict[str, float]:
        allowed = {"expertise", "research_interest", "history", "methodology", "technology", "domain", "preference"}
        if set(value) != allowed or any(number < 0 or number > 1 for number in value.values()):
            raise ValueError("weights must contain exactly the seven non-negative matching weights")
        if abs(sum(value.values()) - 1) > 0.001:
            raise ValueError("matching weights must sum to 1")
        return value


class AIRankingItem(BaseModel):
    """A model ranking for one already-eligible supervisor candidate."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: int = Field(gt=0)
    score: float = Field(ge=0, le=100)
    rationale: str = Field(min_length=1, max_length=600)


class AIRankingPayload(BaseModel):
    """Strict output contract for the Llama 3.1 fit review."""

    model_config = ConfigDict(extra="forbid")

    rankings: list[AIRankingItem] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_unique_candidates(self):
        ids = [item.candidate_id for item in self.rankings]
        if len(ids) != len(set(ids)):
            raise ValueError("each candidate must appear exactly once")
        return self

