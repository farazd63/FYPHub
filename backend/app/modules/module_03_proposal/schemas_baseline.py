from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class BaselineUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_type: str = Field(pattern="^(SHORT|LONG)$")


class MetadataVersionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_metadata: dict[str, Any] = Field(default_factory=dict)
    provenance: Literal["Confirmed academic requirement", "Observed reference property"] = "Observed reference property"
    confirm_duplicate: bool = False


class RuleVersionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: dict[str, Any] | None = None
    provenance: Literal["Confirmed academic requirement", "Observed reference property"] = "Observed reference property"
    confirm_duplicate: bool = False


class BaselineOut(BaseModel):
    id: int
    template_type: str
    filename: str
    version: int
    extraction_status: str
    extracted_rules: dict[str, Any]
    extraction_warnings: list[Any]
    confidence: str | None
    is_active: bool
    sha256: str
    file_size: int
    created_at: datetime
    activated_at: datetime | None


class FormattingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    font_family: str | None = None
    font_size_pt: float | None = None
    heading_styles: dict[str, Any] = Field(default_factory=dict)
    line_spacing: float | str | None = None
    paragraph_spacing: float | None = None
    margins: dict[str, float] = Field(default_factory=dict)
    page_geometry: dict[str, Any] = Field(default_factory=dict)


class CitationRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    style: str | None = None
    figure_caption_convention: str | None = None
    table_caption_convention: str | None = None
    reference_convention: str | None = None


class SectionRule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    required: bool = False
    order: int | None = None
    depth: int | None = None
    word_count_min: int | None = None
    word_count_max: int | None = None
    children: list["SectionRule"] = Field(default_factory=list)


class TemplateRuleSet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_type: Literal["SHORT", "LONG"]
    required_sections: list[SectionRule] = Field(default_factory=list)
    optional_sections: list[SectionRule] = Field(default_factory=list)
    heading_hierarchy: list[str] = Field(default_factory=list)
    expected_section_order: list[str] = Field(default_factory=list)
    formatting: FormattingRules = Field(default_factory=FormattingRules)
    citations: CitationRules = Field(default_factory=CitationRules)
    confidence: str = "UNKNOWN"
    warnings: list[str] = Field(default_factory=list)
    source_checksum: str | None = None
    runtime_metadata: dict[str, Any] = Field(default_factory=dict)


class AIUnavailable(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["UNAVAILABLE"]
    message: str
    runtime: str
    model: str | None = None
    timestamp: datetime


SectionRule.model_rebuild()

