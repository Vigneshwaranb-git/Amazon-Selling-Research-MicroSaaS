"""Review & sentiment schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: str
    rating: int
    review_text: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    reviewed_at: datetime | None = None


class ReviewListResponse(BaseModel):
    items: list[ReviewOut]
    total: int
    page: int
    page_size: int


class ReviewSummaryOut(BaseModel):
    asin: str
    pros: list[str]
    cons: list[str]
    opportunities: list[str]
    generated_at: datetime


class AnalyzeResponse(BaseModel):
    analyzed: int
    summary: ReviewSummaryOut


class PainPointOut(BaseModel):
    label: str
    count: int
    share_pct: float
    example: str


class PainPointsResponse(BaseModel):
    asin: str
    items: list[PainPointOut]
