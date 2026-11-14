"""User settings endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.notifications import NotificationSettings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/notifications", response_model=NotificationSettings)
def get_notifications(user: User = Depends(get_current_user)) -> NotificationSettings:
    return NotificationSettings(bsr_alerts_enabled=user.notify_bsr_alerts)


@router.put("/notifications", response_model=NotificationSettings)
def update_notifications(
    data: NotificationSettings,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationSettings:
    user.notify_bsr_alerts = data.bsr_alerts_enabled
    db.commit()
    return NotificationSettings(bsr_alerts_enabled=user.notify_bsr_alerts)
