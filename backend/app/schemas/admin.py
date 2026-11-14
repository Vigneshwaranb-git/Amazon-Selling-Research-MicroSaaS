"""Pydantic schemas for the admin module."""

from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    is_active: bool
    is_admin: bool
    is_verified: bool
    oauth_provider: str | None = None
    created_at: datetime
    plan: str = "free"


class AdminUserPage(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    page_size: int


class AdminUserUpdate(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class PlanCounts(BaseModel):
    free: int = 0
    pro: int = 0
    business: int = 0


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    new_users_7d: int
    new_users_30d: int
    admins: int
    subscriptions_by_plan: PlanCounts
    active_subscriptions: int
    tracked_products: int
    tracking_lists: int
    scenarios: int
