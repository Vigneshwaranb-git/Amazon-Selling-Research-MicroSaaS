"""Deterministic mock providers for dev/tests (no API keys needed)."""

import hashlib
from datetime import date, timedelta
from decimal import Decimal

from app.services.providers.base import (
    BSRPoint,
    LLMProvider,
    ProductData,
    ProductDataProvider,
    Review,
    ReviewInsights,
    SentimentResult,
)

_CATEGORIES = ["Home & Kitchen", "Sports & Outdoors", "Pet Supplies", "Toys & Games"]
_PAIN_POINTS = [
    "poor durability",
    "hard to assemble",
    "size runs small",
    "weak packaging",
    "battery life",
]
_NEGATIVE_WORDS = {
    "broke",
    "bad",
    "poor",
    "cheap",
    "returned",
    "disappointed",
    "terrible",
}
_POSITIVE_WORDS = {
    "great",
    "love",
    "excellent",
    "perfect",
    "good",
    "sturdy",
    "recommend",
}
_HISTORY_END = date(2025, 1, 1)  # fixed anchor keeps output deterministic


def _seed(value: str) -> int:
    return int(hashlib.sha256(value.encode()).hexdigest()[:12], 16)


class MockProductDataProvider(ProductDataProvider):
    def _build(
        self, asin: str, title: str | None = None, category: str | None = None
    ) -> ProductData:
        s = _seed(asin)
        return ProductData(
            asin=asin,
            title=title or f"Mock Product {asin}",
            brand=f"Brand{s % 50}",
            category=category or _CATEGORIES[s % len(_CATEGORIES)],
            price=Decimal(1500 + s % 4000) / 100,
            bsr=1000 + s % 50000,
            rating=round(3.5 + (s % 15) / 10, 1),
            review_count=50 + s % 5000,
            monthly_sales_estimate=100 + s % 3000,
            seller_count=1 + s % 20,
            image_url=f"https://example.com/images/{asin}.jpg",
        )

    async def get_product(self, asin: str) -> ProductData | None:
        if not asin or len(asin) != 10:
            return None
        return self._build(asin)

    async def search_products(
        self, keyword: str, category: str | None = None, limit: int = 20
    ) -> list[ProductData]:
        base = _seed(keyword)
        return [
            self._build(f"B{(base + i) % 10**9:09d}", f"{keyword.title()} #{i + 1}", category)
            for i in range(limit)
        ]

    async def get_bsr_history(self, asin: str, days: int = 30) -> list[BSRPoint]:
        product = self._build(asin)
        s = _seed(asin)
        points: list[BSRPoint] = []
        for i in range(days):
            wobble = ((s >> (i % 16)) % 21 - 10) * product.bsr // 100
            points.append(
                BSRPoint(
                    day=_HISTORY_END - timedelta(days=days - i),
                    bsr=max(1, product.bsr + wobble),
                    price=product.price,
                )
            )
        return points

    async def get_reviews(self, asin: str, limit: int = 50) -> list[Review]:
        s = _seed(asin)
        reviews: list[Review] = []
        for i in range(limit):
            rating = 1 + (s + i * 7) % 5
            pain = _PAIN_POINTS[(s + i) % len(_PAIN_POINTS)]
            body = "Great value, love it." if rating >= 4 else f"Disappointed, {pain}."
            reviews.append(
                Review(
                    id=f"{asin}-{i}",
                    rating=rating,
                    title=f"Review {i + 1}",
                    body=body,
                    # Newest first, spread deterministically over roughly the last year.
                    reviewed_at=_HISTORY_END - timedelta(days=i * 7 + (s + i) % 7),
                )
            )
        return reviews


def _score(reviews: list[Review]) -> tuple[float, str]:
    score = 0
    for r in reviews:
        words = set(r.body.lower().replace(",", " ").replace(".", " ").split())
        score += len(words & _POSITIVE_WORDS) - len(words & _NEGATIVE_WORDS)
    normalized = max(-1.0, min(1.0, score / len(reviews)))
    label = "positive" if normalized > 0.2 else "negative" if normalized < -0.2 else "neutral"
    return round(normalized, 2), label


class MockLLMProvider(LLMProvider):
    async def analyze_sentiment(self, reviews: list[Review]) -> SentimentResult:
        if not reviews:
            return SentimentResult(score=0.0, label="neutral")
        score, label = _score(reviews)
        return SentimentResult(
            score=score, label=label, pain_points=await self.extract_pain_points(reviews)
        )

    async def analyze_sentiment_batch(self, reviews: list[Review]) -> list[SentimentResult]:
        """Score every review in a single (mock) request; result[i] belongs to reviews[i]."""
        results: list[SentimentResult] = []
        for review in reviews:
            score, label = _score([review])
            results.append(
                SentimentResult(
                    score=score,
                    label=label,
                    pain_points=await self.extract_pain_points([review]),
                )
            )
        return results

    async def summarize(self, text: str, max_words: int = 100) -> str:
        return " ".join(text.split()[:max_words])

    async def extract_pain_points(self, reviews: list[Review], limit: int = 5) -> list[str]:
        counts: dict[str, int] = {}
        for r in reviews:
            if r.rating <= 2:
                for p in _PAIN_POINTS:
                    if p in r.body.lower():
                        counts[p] = counts.get(p, 0) + 1
        ranked = sorted(counts, key=lambda k: (-counts[k], k))
        return ranked[:limit]

    async def generate_insights(self, reviews: list[Review]) -> ReviewInsights:
        positive = [r for r in reviews if r.rating >= 4]
        pros = ["Good value for money", "Customers praise overall quality"] if positive else []
        cons = [p.capitalize() for p in await self.extract_pain_points(reviews, limit=3)]
        opportunities = [f"Improve: {c.lower()}" for c in cons]
        return ReviewInsights(pros=pros, cons=cons, opportunities=opportunities)
