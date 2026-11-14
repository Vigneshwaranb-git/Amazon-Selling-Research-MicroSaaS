"""Tracking list business logic. All access is scoped to the owning user."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.exceptions import ConflictError, NotFoundError
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.services.product_service import attach_margin


def _name_taken(db: Session, user_id: int, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(TrackingList.id).where(
        TrackingList.user_id == user_id, func.lower(TrackingList.name) == name.lower()
    )
    if exclude_id is not None:
        stmt = stmt.where(TrackingList.id != exclude_id)
    return db.execute(stmt).first() is not None


def get_owned_list(db: Session, user_id: int, list_id: int) -> TrackingList:
    """404 (not 403) when the list is missing or belongs to someone else."""
    tl = db.execute(
        select(TrackingList).where(TrackingList.id == list_id, TrackingList.user_id == user_id)
    ).scalar_one_or_none()
    if tl is None:
        raise NotFoundError("Tracking list")
    return tl


def product_count(db: Session, tl: TrackingList) -> int:
    return db.execute(
        select(func.count(TrackedProduct.id)).where(TrackedProduct.tracking_list_id == tl.id)
    ).scalar_one()


def list_lists(db: Session, user_id: int) -> list[tuple[TrackingList, int]]:
    stmt = (
        select(TrackingList, func.count(TrackedProduct.id))
        .outerjoin(TrackedProduct, TrackedProduct.tracking_list_id == TrackingList.id)
        .where(TrackingList.user_id == user_id)
        .group_by(TrackingList.id)
        .order_by(TrackingList.created_at.desc(), TrackingList.id.desc())
    )
    return [(tl, n) for tl, n in db.execute(stmt).all()]


def create_list(db: Session, user_id: int, name: str) -> TrackingList:
    if _name_taken(db, user_id, name):
        raise ConflictError("A tracking list with this name already exists")
    tl = TrackingList(user_id=user_id, name=name)
    db.add(tl)
    db.commit()
    db.refresh(tl)
    return tl


def rename_list(db: Session, user_id: int, list_id: int, name: str) -> TrackingList:
    tl = get_owned_list(db, user_id, list_id)
    if _name_taken(db, user_id, name, exclude_id=tl.id):
        raise ConflictError("A tracking list with this name already exists")
    tl.name = name
    db.commit()
    db.refresh(tl)
    return tl


def delete_list(db: Session, user_id: int, list_id: int) -> None:
    tl = get_owned_list(db, user_id, list_id)
    db.delete(tl)
    db.commit()


def list_products(db: Session, tl: TrackingList) -> list[Product]:
    rows = (
        db.execute(
            select(Product)
            .join(TrackedProduct, TrackedProduct.product_id == Product.id)
            .where(TrackedProduct.tracking_list_id == tl.id)
            .order_by(TrackedProduct.added_at.desc(), TrackedProduct.id.desc())
        )
        .scalars()
        .all()
    )
    return [attach_margin(p) for p in rows]


def add_product(db: Session, tl: TrackingList, product: Product) -> None:
    exists = db.execute(
        select(TrackedProduct.id).where(
            TrackedProduct.tracking_list_id == tl.id, TrackedProduct.product_id == product.id
        )
    ).first()
    if exists is not None:
        raise ConflictError("Product is already in this list")
    db.add(TrackedProduct(tracking_list_id=tl.id, product_id=product.id))
    db.commit()


def remove_product(db: Session, tl: TrackingList, asin: str) -> None:
    tp = db.execute(
        select(TrackedProduct)
        .join(Product, Product.id == TrackedProduct.product_id)
        .where(TrackedProduct.tracking_list_id == tl.id, Product.asin == asin)
    ).scalar_one_or_none()
    if tp is None:
        raise NotFoundError("Tracked product")
    db.delete(tp)
    db.commit()
