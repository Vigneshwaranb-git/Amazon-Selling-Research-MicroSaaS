"""Product tracker endpoints."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.product import (
    ASIN_PATTERN,
    ProductDetail,
    ProductHistoryResponse,
    ProductListResponse,
    ProductOut,
    SnapshotOut,
)
from app.services import product_service
from app.services.product_service import ProductFilters
from app.services.providers import get_product_data_provider
from app.services.providers.base import ProductDataProvider

router = APIRouter(prefix="/products", tags=["products"])

AsinPath = Annotated[str, Path(pattern=ASIN_PATTERN, min_length=10, max_length=10)]


def get_filters(
    category: Annotated[str | None, Query(max_length=255)] = None,
    min_margin: Annotated[float | None, Query(ge=-100, le=100)] = None,
    max_saturation: Annotated[int | None, Query(ge=0, le=100)] = None,
    min_trend: Annotated[int | None, Query(ge=0, le=100)] = None,
    search: Annotated[str | None, Query(max_length=100)] = None,
    sort_by: Literal["bsr", "sales", "revenue", "price", "trend", "saturation"] = "bsr",
    sort_dir: Literal["asc", "desc"] = "asc",
) -> ProductFilters:
    return ProductFilters(
        category=category,
        min_margin=min_margin,
        max_saturation=max_saturation,
        min_trend=min_trend,
        search=search,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    filters: ProductFilters = Depends(get_filters),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    provider: ProductDataProvider = Depends(get_product_data_provider),
    _user: User = Depends(get_current_user),
) -> ProductListResponse:
    await product_service.ensure_seeded(db, provider)
    items, total = product_service.list_products(db, filters, page, page_size)
    return ProductListResponse(
        items=[ProductOut.model_validate(p) for p in items],
        total=total,
        page=page,
        page_size=page_size,
    )


# Declared before /{asin} so "export" is not captured as an ASIN.
@router.get("/export")
def export_products(
    filters: ProductFilters = Depends(get_filters),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> Response:
    content = product_service.products_to_csv(product_service.list_for_export(db, filters))
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="products.csv"'},
    )


@router.get("/{asin}", response_model=ProductDetail)
async def get_product(
    asin: AsinPath,
    db: Session = Depends(get_db),
    provider: ProductDataProvider = Depends(get_product_data_provider),
    _user: User = Depends(get_current_user),
) -> ProductDetail:
    product = await product_service.get_or_fetch_product(db, provider, asin)
    detail = ProductDetail.model_validate(product)
    detail.snapshot_count = product_service.snapshot_count(db, product)
    return detail


@router.get("/{asin}/history", response_model=ProductHistoryResponse)
async def get_product_history(
    asin: AsinPath,
    limit: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    provider: ProductDataProvider = Depends(get_product_data_provider),
    _user: User = Depends(get_current_user),
) -> ProductHistoryResponse:
    product = await product_service.get_or_fetch_product(db, provider, asin)
    snaps = product_service.get_history(db, product, limit)
    return ProductHistoryResponse(
        asin=product.asin, snapshots=[SnapshotOut.model_validate(s) for s in snaps]
    )
