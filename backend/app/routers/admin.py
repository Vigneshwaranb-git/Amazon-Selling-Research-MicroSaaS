"""Admin endpoints (admin-only, enforced server-side)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin, get_db
from app.models.user import User
from app.schemas.admin import AdminStats, AdminUserOut, AdminUserPage, AdminUserUpdate
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(get_current_admin)])


@router.get("/users", response_model=AdminUserPage)
def list_users(
    search: str | None = Query(default=None, max_length=100),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AdminUserPage:
    return admin_service.list_users(db, search, page, page_size)


@router.put("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: AdminUserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> AdminUserOut:
    return admin_service.update_user(db, admin, user_id, body)


@router.get("/stats", response_model=AdminStats)
def get_stats(db: Session = Depends(get_db)) -> AdminStats:
    return admin_service.get_stats(db)
