"""Provider factory: real providers when keys exist (Phase 2), mocks otherwise."""

import logging

from app.config import settings
from app.services.providers.base import LLMProvider, ProductDataProvider
from app.services.providers.mock import MockLLMProvider, MockProductDataProvider

logger = logging.getLogger(__name__)


def get_product_data_provider() -> ProductDataProvider:
    if settings.AMAZON_DATA_API_KEY:
        logger.warning("Real product data provider not implemented yet; using mock")
    return MockProductDataProvider()


def get_llm_provider() -> LLMProvider:
    if settings.LLM_API_KEY:
        logger.warning("Real LLM provider not implemented yet; using mock")
    return MockLLMProvider()


__all__ = [
    "LLMProvider",
    "MockLLMProvider",
    "MockProductDataProvider",
    "ProductDataProvider",
    "get_llm_provider",
    "get_product_data_provider",
]
