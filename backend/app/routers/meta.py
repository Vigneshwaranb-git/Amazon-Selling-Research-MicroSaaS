"""Public metadata endpoints (no auth)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.services.providers import DatasetProductDataProvider, get_product_data_provider

router = APIRouter(prefix="/meta", tags=["meta"])


class DataSourceOut(BaseModel):
    provider: str
    attribution: str | None
    data_as_of: str | None
    notes: list[str]


@router.get("/data-source", response_model=DataSourceOut)
async def data_source() -> DataSourceOut:
    """Which data source feeds the app, its attribution and its honest limitations."""
    notes: list[str] = []
    if settings.LLM_PROVIDER == "lexicon":
        notes.append("Review sentiment and pain points come from a rule-based lexicon, not an LLM.")
    provider = get_product_data_provider()  # raises a clear 503 if the dataset is missing
    if isinstance(provider, DatasetProductDataProvider):
        return DataSourceOut(
            provider="dataset",
            attribution=provider.info.get("attribution"),
            data_as_of=provider.data_as_of.isoformat(),
            notes=[*provider.data_source_notes(), *notes],
        )
    return DataSourceOut(
        provider="mock",
        attribution=None,
        data_as_of=None,
        notes=["Demo data is simulated: products, prices, ranks and reviews are not real.", *notes],
    )
