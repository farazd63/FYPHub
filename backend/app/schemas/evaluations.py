"""Request and response contracts for role-based FYP evaluation."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationCategory(StrEnum):
    FINAL_PRESENTATION = "FINAL_PRESENTATION"
    MID_REVIEW = "MID_REVIEW"
    SUPERVISOR_EVALUATION = "SUPERVISOR_EVALUATION"
    PROJECT_DOCUMENTATION = "PROJECT_DOCUMENTATION"
    PROPOSAL = "PROPOSAL"


class EvaluationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    RETURNED = "RETURNED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"


MAXIMUM_MARKS = {
    EvaluationCategory.FINAL_PRESENTATION: 30,
    EvaluationCategory.MID_REVIEW: 30,
    EvaluationCategory.SUPERVISOR_EVALUATION: 10,
    EvaluationCategory.PROJECT_DOCUMENTATION: 20,
    EvaluationCategory.PROPOSAL: 10,
}


class EvaluationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    team_id: int | None = Field(default=None, gt=0)
    evaluation_category: EvaluationCategory
    obtained_marks: int | None = Field(default=None, ge=0)
    feedback: str | None = Field(default=None, max_length=10000)
    submit: bool = False

    @field_validator("feedback")
    @classmethod
    def normalize_feedback(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_target_and_marks(self):
        group_id = self.group_id or self.team_id
        if (self.student_id is None) == (group_id is None):
            raise ValueError("Provide exactly one student_id or group_id target.")
        maximum = MAXIMUM_MARKS[self.evaluation_category]
        if self.obtained_marks is not None and self.obtained_marks > maximum:
            raise ValueError(f"Marks cannot exceed the maximum of {maximum}.")
        return self


class EvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    student_id: int | None
    group_id: int | None
    evaluator_id: int
    evaluator_role: str
    evaluation_category: str
    maximum_marks: int
    obtained_marks: int | None
    feedback: str | None
    status: str
    returned_reason: str | None
    submitted_at: datetime | None
    approved_at: datetime | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AssignmentMemberOut(BaseModel):
    id: int
    full_name: str
    registration_number: str
    university_email: str


class EvaluationAssignmentOut(BaseModel):
    group_id: int
    academic_cycle_id: int
    students: list[AssignmentMemberOut]
    categories: list[str]


class EvaluationReturn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=5000)

    @field_validator("reason")
    @classmethod
    def reason_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A correction reason is required.")
        return value


class EvaluationCorrectionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new_marks: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=5000)

    @field_validator("reason")
    @classmethod
    def correction_reason_nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A correction reason is required.")
        return value


class EvaluationAggregationWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evaluation_category: EvaluationCategory
    method: str = Field(pattern="^(AVERAGE|MAXIMUM|MEDIAN)$")


class EvaluationAggregationOut(BaseModel):
    id: int
    evaluation_category: str
    method: str
    is_active: bool


class ResultCategoryOut(BaseModel):
    category: str
    maximum_marks: int
    obtained_marks: float | None
    status: str
    evaluator_ids: list[int]
    feedback: list[str]


class ConsolidatedResultOut(BaseModel):
    student_id: int
    group_id: int | None
    student_name: str
    registration_number: str | None
    categories: list[ResultCategoryOut]
    total_marks: float
    maximum_marks: int
    percentage: float
    grade: str | None
    gpa: float | None
    published: bool
