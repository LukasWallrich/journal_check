"""Pydantic models for structured LLM output."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class GuidelinesAnalysis(BaseModel):
    """Structured analysis of journal author guidelines."""

    journal_name: str = Field(description="Name of the journal")

    # Content validation fields
    is_author_guidelines: bool = Field(
        description="Whether this content is actually author/submission guidelines (not a landing page, error page, or unrelated content)"
    )
    content_type: Literal[
        "journal_specific_guidelines",
        "publisher_generic_guidelines",
        "landing_page",
        "error_page",
        "unrelated_content",
    ] = Field(
        description="What type of content this appears to be"
    )
    guidelines_specificity_notes: Optional[str] = Field(
        default=None,
        description="Notes on whether guidelines are specific to this journal or generic publisher-wide guidelines",
    )

    pilot_study_mentioned: bool = Field(
        description="Whether pilot studies are mentioned in the guidelines"
    )
    pilot_study_stance: Optional[
        Literal["required", "encouraged", "accepted", "discouraged", "not_mentioned"]
    ] = Field(
        default=None,
        description="The journal's stance on pilot studies if mentioned",
    )
    pilot_study_quotes: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Direct quotes mentioning pilot studies (max 3)",
    )

    feasibility_study_mentioned: bool = Field(
        description="Whether feasibility studies are mentioned in the guidelines"
    )
    feasibility_study_stance: Optional[
        Literal["required", "encouraged", "accepted", "discouraged", "not_mentioned"]
    ] = Field(
        default=None,
        description="The journal's stance on feasibility studies if mentioned",
    )
    feasibility_study_quotes: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Direct quotes mentioning feasibility studies (max 3)",
    )

    preliminary_data_mentioned: bool = Field(
        description="Whether preliminary data/studies are mentioned"
    )
    registered_reports_mentioned: bool = Field(
        description="Whether registered reports are mentioned as a submission type"
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence in the analysis (0-1)",
    )
    analysis_notes: Optional[str] = Field(
        default=None,
        description="Additional notes about the analysis or ambiguities",
    )


class JournalInfo(BaseModel):
    """Journal information from SCImago/OpenAlex."""

    title: str
    issn: str
    publisher: Optional[str] = None
    sjr_rank: Optional[int] = None
    homepage_url: Optional[str] = None
    guidelines_url: Optional[str] = None
