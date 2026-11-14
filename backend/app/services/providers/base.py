"""Abstract provider interfaces and shared data types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ProductData:
    asin: str
    title: str
    brand: str
    category: str
    price: Decimal
    bsr: int
    rating: float
    review_count: int
    monthly_sales_estimate: int
    seller_count: int
    image_url: str = ""


@dataclass(frozen=True)
class BSRPoint:
    day: date
    bsr: int
    price: Decimal


@dataclass(frozen=True)
class Review:
    id: str
    rating: int
    title: str
    body: str


@dataclass(frozen=True)
class SentimentResult:
    score: float  # -1.0 .. 1.0
    label: str  # positive | neutral | negative
    pain_points: list[str] = field(default_factory=list)


class ProductDataProvider(ABC):
    """Swappable Amazon data source (Keepa / Rainforest / SP-API)."""

    @abstractmethod
    async def get_product(self, asin: str) -> ProductData | None: ...

    @abstractmethod
    async def search_products(
        self, keyword: str, category: str | None = None, limit: int = 20
    ) -> list[ProductData]: ...

    @abstractmethod
    async def get_bsr_history(self, asin: str, days: int = 30) -> list[BSRPoint]: ...

    @abstractmethod
    async def get_reviews(self, asin: str, limit: int = 50) -> list[Review]: ...


class LLMProvider(ABC):
    """Swappable LLM backend for sentiment and summaries."""

    @abstractmethod
    async def analyze_sentiment(self, reviews: list[Review]) -> SentimentResult: ...

    @abstractmethod
    async def summarize(self, text: str, max_words: int = 100) -> str: ...

    @abstractmethod
    async def extract_pain_points(self, reviews: list[Review], limit: int = 5) -> list[str]: ...
