"""Provider factory: mock by default; open dataset / lexicon LLM when opted in via settings."""

import logging

from app.config import settings
from app.data import schema
from app.services.providers.base import LLMProvider, ProductDataProvider
from app.services.providers.dataset import DatasetConfigError, DatasetProductDataProvider
from app.services.providers.lexicon import LexiconLLMProvider
from app.services.providers.mock import MockLLMProvider, MockProductDataProvider

logger = logging.getLogger(__name__)

_dataset_provider: DatasetProductDataProvider | None = None


def _dataset_provider_for(path: str) -> DatasetProductDataProvider:
    """Cached provider per dataset path (and file mtime, so a re-import is picked up)."""
    global _dataset_provider
    current = _dataset_provider
    resolved = schema.resolve_dataset_path(path)
    try:
        mtime = resolved.stat().st_mtime_ns
    except OSError:
        mtime = None
    if current is None or current.path != resolved or getattr(current, "_mtime", None) != mtime:
        current = DatasetProductDataProvider(path)  # raises DatasetConfigError with the fix
        current._mtime = mtime  # type: ignore[attr-defined]
        _dataset_provider = current
        logger.info("Using open dataset provider: %s (as of %s)", path, current.data_as_of)
    return current


def get_product_data_provider() -> ProductDataProvider:
    if settings.DATA_PROVIDER == "dataset":
        return _dataset_provider_for(settings.DATASET_PATH)
    if settings.AMAZON_DATA_API_KEY:
        logger.warning("Real product data provider not implemented yet; using mock")
    return MockProductDataProvider()


def get_llm_provider() -> LLMProvider:
    if settings.LLM_PROVIDER == "lexicon":
        return LexiconLLMProvider()
    if settings.LLM_API_KEY:
        logger.warning("Real LLM provider not implemented yet; using mock")
    return MockLLMProvider()


__all__ = [
    "DatasetConfigError",
    "DatasetProductDataProvider",
    "LLMProvider",
    "LexiconLLMProvider",
    "MockLLMProvider",
    "MockProductDataProvider",
    "ProductDataProvider",
    "get_llm_provider",
    "get_product_data_provider",
    "schema",
]
