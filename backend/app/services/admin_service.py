"""Admin business logic: user management and platform statistics."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.exceptions import AppException, NotFoundError
from app.models.cost_model import CostModel
from app.models.subscription import Subscription
from app.models.tracking_list import TrackedProduct, TrackingList
from app.models.user import User
from app.schemas.admin import (
    AdminStats,
    AdminUserOut,
    AdminUserPage,
    AdminUserUpdate,
    PlanCounts,
)
from app.services import auth_service

logger = logging.getLogger(__name__)

LIVE_STATUSES = ("active", "past_due", "paused")
_ESC = "\\"


def _plan_subquery() -> Any:
    """Correlated scalar: plan of the user's newest live subscription."""
    return (
        select(Subscription.plan)
        .where(Subscription.user_id == User.id, Subscription.status.in_(LIVE_STATUSES))
        .order_by(Subscription.id.desc())
        .limit(1)
        .correlate(User)
        .scalar_subquery()
    )


def _escape_like(term: str) -> str:
    return term.replace(_ESC, _ESC * 2).replace("%", _ESC + "%").replace("_", _ESC + "_")


def _to_out(user: User, plan: str | None) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_admin=user.is_admin,
        is_verified=user.is_verified,
        oauth_provider=user.oauth_provider,
        created_at=user.created_at,
        plan=plan or "free",
    )


def list_users(db: Session, search: str | None, page: int, page_size: int) -> AdminUserPage:
    filters: list[ColumnElement[bool]] = []
    term = (search or "").strip()
    if term:
        pattern = f"%{_escape_like(term.lower())}%"
        filters.append(
            func.lower(User.email).like(pattern, escape=_ESC)
            | func.lower(func.coalesce(User.full_name, "")).like(pattern, escape=_ESC)
        )
    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    rows = db.execute(
        select(User, _plan_subquery().label("plan"))
        .where(*filters)
        .order_by(User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return AdminUserPage(
        items=[_to_out(u, plan) for u, plan in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def update_user(db: Session, admin: User, user_id: int, data: AdminUserUpdate) -> AdminUserOut:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User")
    if user.id == admin.id and (data.is_active is False or data.is_admin is False):
        raise AppException(
            "Admins cannot deactivate or demote themselves", "SELF_MODIFICATION", 400
        )
    deactivated = data.is_active is False and user.is_active
    if data.is_active is not None:
        user.is_active = data.is_active
    if data.is_admin is not None:
        user.is_admin = data.is_admin
    db.commit()
    if deactivated:
        auth_service.revoke_all_user_tokens(db, user.id)
        logger.info("Admin %s deactivated user %s", admin.id, user.id)
    db.refresh(user)
    plan = db.scalar(
        select(Subscription.plan)
        .where(Subscription.user_id == user.id, Subscription.status.in_(LIVE_STATUSES))
        .order_by(Subscription.id.desc())
        .limit(1)
    )
    return _to_out(user, plan)


def get_stats(db: Session) -> AdminStats:
    now = datetime.now(UTC)
    users = db.execute(
        select(
            func.count(User.id),
            func.count(User.id).filter(User.is_active.is_(True)),
            func.count(User.id).filter(User.created_at >= now - timedelta(days=7)),
            func.count(User.id).filter(User.created_at >= now - timedelta(days=30)),
            func.count(User.id).filter(User.is_admin.is_(True)),
        )
    ).one()
    total_users = users[0]

    # newest live subscription per user -> one plan per subscribed user
    newest = (
        select(func.max(Subscription.id))
        .where(Subscription.status.in_(LIVE_STATUSES))
        .group_by(Subscription.user_id)
        .scalar_subquery()
    )
    by_plan: dict[str, int] = dict(
        db.execute(
            select(Subscription.plan, func.count(Subscription.id))
            .where(Subscription.id.in_(newest))
            .group_by(Subscription.plan)
        )
        .tuples()
        .all()
    )
    paid = {k: int(v) for k, v in by_plan.items() if k != "free"}
    active_subs = sum(paid.values())
    plans = PlanCounts(
        free=max(total_users - active_subs, 0),
        pro=paid.get("pro", 0),
        business=paid.get("business", 0),
    )
    return AdminStats(
        total_users=total_users,
        active_users=users[1],
        new_users_7d=users[2],
        new_users_30d=users[3],
        admins=users[4],
        subscriptions_by_plan=plans,
        active_subscriptions=active_subs,
        tracked_products=db.scalar(select(func.count(TrackedProduct.id))) or 0,
        tracking_lists=db.scalar(select(func.count(TrackingList.id))) or 0,
        scenarios=db.scalar(select(func.count(CostModel.id))) or 0,
    )
