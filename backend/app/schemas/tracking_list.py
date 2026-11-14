"""Tracking list schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.product import Asin, ProductOut


class TrackingListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v


class TrackingListUpdate(TrackingListCreate):
    pass


class AddProductRequest(BaseModel):
    asin: Asin


class TrackingListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime
    product_count: int = 0


class TrackingListDetail(TrackingListOut):
    products: list[ProductOut] = Field(default_factory=list)
