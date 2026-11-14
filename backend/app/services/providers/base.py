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
    # Optional provider-computed scores (0-100). When set they replace the generic
    # snapshot-derived trend and the generic saturation formula (real-data providers).
    saturation_score: int | None = None
    trend_score: int | None = None
    # Date the price/BSR were captured, when the source is a static dataset snapshot.
    data_as_of: date | None = None


@dataclass(frozen=True)
class BSRPoint:
    day: date
    bsr: int
    price: Decimal
    estimated_sales: int | None = None  # provider's own estimate; None -> generic heuristic


@dataclass(frozen=True)
class Review:
    id: str
    rating: int
    title: str
    body: str
    reviewed_at: date | None = None


@dataclass(frozen=True)
class SentimentResult:
    score: float  # -1.0 .. 1.0
    label: str  # positive | neutral | negative
    pain_points: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewInsights:
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    opportunities: list[str] = field(default_factory=list)


class ProductDataProvider(ABC):
    """Swappable Amazon data source (Keepa / Rainforest / SP-API / open dataset)."""

    # False for static datasets: BSR/price never change between runs, so the snapshot job must
    # not append "new" snapshots (that would fabricate a time series of identical points).
    supports_live_snapshots: bool = True

    async def seed_asins(self, limit: int) -> list[str] | None:
        """ASINs to seed an empty product list with, or None to use the keyword search."""
        return None

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

    async def analyze_sentiment_batch(self, reviews: list[Review]) -> list[SentimentResult]:
        """Score each review individually; result[i] belongs to reviews[i].

        Real providers should override this to score the whole list in one request. The
        default falls back to one call per review.
        """
        return [await self.analyze_sentiment([r]) for r in reviews]

    @abstractmethod
    async def summarize(self, text: str, max_words: int = 100) -> str: ...

    @abstractmethod
    async def extract_pain_points(self, reviews: list[Review], limit: int = 5) -> list[str]: ...

    @abstractmethod
    async def generate_insights(self, reviews: list[Review]) -> ReviewInsights: ...
