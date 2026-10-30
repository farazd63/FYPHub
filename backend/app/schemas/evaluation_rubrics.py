"""Strict request and response schemas for draft Evaluation Criteria."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RubricCriterionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    order: int = Field(ge=1)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Criterion name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RubricVersionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4000)
    criteria: list[RubricCriterionWrite] = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def nonblank_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Evaluation criteria name must not be blank.")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def unique_orders(self) -> "RubricVersionWrite":
        orders = [criterion.order for criterion in self.criteria]
        if len(orders) != len(set(orders)):
            raise ValueError("Criterion order values must be unique.")
        return self


class RubricCriterionOut(BaseModel):
    id: int
    name: str
    description: str | None
    order: int


class RubricVersionOut(BaseModel):
    id: int
    version_number: int
    name: str
    description: str | None
    created_at: datetime
    criteria: list[RubricCriterionOut]


class RubricDetailOut(BaseModel):
    id: int
    created_at: datetime
    versions: list[RubricVersionOut]


class RubricListOut(BaseModel):
    id: int
    name: str
    description: str | None
    latest_version_number: int
    created_at: datetime
