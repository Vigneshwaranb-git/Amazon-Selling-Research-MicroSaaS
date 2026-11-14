"""Notification settings schemas."""

from pydantic import BaseModel


class NotificationSettings(BaseModel):
    bsr_alerts_enabled: bool
