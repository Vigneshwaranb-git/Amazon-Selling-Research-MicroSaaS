"""Tracking list endpoints (all scoped to the authenticated user)."""

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.routers.products import AsinPath
from app.schemas.product import ProductOut
from app.schemas.tracking_list import (
    AddProductRequest,
    TrackingListCreate,
    TrackingListDetail,
    TrackingListOut,
    TrackingListUpdate,
)
from app.services import product_service, tracking_service
from app.services.providers import get_product_data_provider
from app.services.providers.base import ProductDataProvider

router = APIRouter(prefix="/tracking-lists", tags=["tracking-lists"])


def _detail(db: Session, user: User, list_id: int) -> TrackingListDetail:
    tl = tracking_service.get_owned_list(db, user.id, list_id)
    products = tracking_service.list_products(db, tl)
    return TrackingListDetail(
        id=tl.id,
        name=tl.name,
        created_at=tl.created_at,
        product_count=len(products),
        products=[ProductOut.model_validate(p) for p in products],
    )


@router.get("", response_model=list[TrackingListOut])
def list_tracking_lists(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> list[TrackingListOut]:
    return [
        TrackingListOut(id=tl.id, name=tl.name, created_at=tl.created_at, product_count=n)
        for tl, n in tracking_service.list_lists(db, user.id)
    ]


@router.post("", response_model=TrackingListOut, status_code=status.HTTP_201_CREATED)
def create_tracking_list(
    body: TrackingListCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrackingListOut:
    tl = tracking_service.create_list(db, user.id, body.name)
    return TrackingListOut(id=tl.id, name=tl.name, created_at=tl.created_at, product_count=0)


@router.get("/{list_id}", response_model=TrackingListDetail)
def get_tracking_list(
    list_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> TrackingListDetail:
    return _detail(db, user, list_id)


@router.put("/{list_id}", response_model=TrackingListOut)
def rename_tracking_list(
    list_id: int,
    body: TrackingListUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TrackingListOut:
    tl = tracking_service.rename_list(db, user.id, list_id, body.name)
    return TrackingListOut(
        id=tl.id,
        name=tl.name,
        created_at=tl.created_at,
        product_count=tracking_service.product_count(db, tl),
    )


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tracking_list(
    list_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    tracking_service.delete_list(db, user.id, list_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{list_id}/products",
    response_model=TrackingListDetail,
    status_code=status.HTTP_201_CREATED,
)
async def add_product_to_list(
    list_id: int,
    body: AddProductRequest,
    db: Session = Depends(get_db),
    provider: ProductDataProvider = Depends(get_product_data_provider),
    user: User = Depends(get_current_user),
) -> TrackingListDetail:
    tl = tracking_service.get_owned_list(db, user.id, list_id)
    product = await product_service.get_or_fetch_product(db, provider, body.asin)
    tracking_service.add_product(db, tl, product)
    return _detail(db, user, list_id)


@router.delete("/{list_id}/products/{asin}", status_code=status.HTTP_204_NO_CONTENT)
def remove_product_from_list(
    list_id: int,
    asin: AsinPath,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    tl = tracking_service.get_owned_list(db, user.id, list_id)
    tracking_service.remove_product(db, tl, asin)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
