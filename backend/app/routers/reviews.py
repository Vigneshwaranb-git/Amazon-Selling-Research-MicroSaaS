"""Review & sentiment monitor endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.rate_limit import limiter
from app.routers.products import AsinPath
from app.schemas.review import (
    AnalyzeResponse,
    PainPointsResponse,
    ReviewListResponse,
    ReviewOut,
    ReviewSummaryOut,
)
from app.services import review_service
from app.services.providers import get_llm_provider, get_product_data_provider
from app.services.providers.base import LLMProvider, ProductDataProvider

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/{asin}", response_model=ReviewListResponse)
def list_reviews(
    asin: AsinPath,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ReviewListResponse:
    product = review_service.get_product_or_404(db, asin)
    rows, total = review_service.list_reviews(db, product, rating, keyword, page, page_size)
    return ReviewListResponse(
        items=[ReviewOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/{asin}/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze_reviews(
    request: Request,
    asin: AsinPath,
    db: Session = Depends(get_db),
    data_provider: ProductDataProvider = Depends(get_product_data_provider),
    llm: LLMProvider = Depends(get_llm_provider),
    _user: User = Depends(get_current_user),
) -> AnalyzeResponse:
    analyzed, summary, product = await review_service.analyze_product(db, data_provider, llm, asin)
    return AnalyzeResponse(
        analyzed=analyzed, summary=review_service.to_summary_out(product.asin, summary)
    )


@router.get("/{asin}/summary", response_model=ReviewSummaryOut)
def get_summary(
    asin: AsinPath,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> ReviewSummaryOut:
    product = review_service.get_product_or_404(db, asin)
    return review_service.to_summary_out(product.asin, review_service.get_summary(db, product))


@router.get("/{asin}/pain-points", response_model=PainPointsResponse)
def get_pain_points(
    asin: AsinPath,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PainPointsResponse:
    product = review_service.get_product_or_404(db, asin)
    return PainPointsResponse(asin=product.asin, items=review_service.pain_point_stats(db, product))
