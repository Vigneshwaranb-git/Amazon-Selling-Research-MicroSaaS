"""Sentiment + pain-point extraction via the LLMProvider (PII-safe)."""

import logging
import re
from dataclasses import dataclass

from app.services.providers.base import LLMProvider, Review, ReviewInsights, SentimentResult

logger = logging.getLogger(__name__)

MAX_REVIEW_CHARS = 1000
MAX_TITLE_CHARS = 150
MAX_REVIEWS = 100
SENTIMENT_BATCH_SIZE = 20

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d\s().-]{7,}\d(?!\w)")


def scrub(text: str, max_chars: int) -> str:
    """Remove emails/URLs/phone numbers and truncate before text leaves the system."""
    text = _EMAIL_RE.sub("[email]", text)
    text = _URL_RE.sub("[url]", text)
    text = _PHONE_RE.sub("[phone]", text)
    return text[:max_chars]


def sanitize_reviews(reviews: list[Review]) -> list[Review]:
    """Anonymised, length-limited copies; provider ids are replaced by ordinals."""
    return [
        Review(
            id=str(i),
            rating=r.rating,
            title=scrub(r.title, MAX_TITLE_CHARS),
            body=scrub(r.body, MAX_REVIEW_CHARS),
        )
        for i, r in enumerate(reviews[:MAX_REVIEWS])
    ]


@dataclass(frozen=True)
class ReviewAnalysis:
    reviews: list[Review]  # the (capped) reviews that were analysed
    per_review: dict[str, SentimentResult]  # keyed by original provider review id
    insights: ReviewInsights


async def _score_chunk(llm: LLMProvider, chunk: list[Review]) -> list[SentimentResult]:
    """One batched provider call; if it fails or misreturns, fall back to one call per review."""
    try:
        results = await llm.analyze_sentiment_batch(chunk)
        if len(results) == len(chunk):
            return results
        logger.warning(
            "Sentiment batch returned %d results for %d reviews", len(results), len(chunk)
        )
    except Exception:
        logger.warning("Sentiment batch failed; falling back to per-review calls", exc_info=True)
    return [await llm.analyze_sentiment([review]) for review in chunk]


async def analyze_reviews(llm: LLMProvider, reviews: list[Review]) -> ReviewAnalysis:
    reviews = reviews[:MAX_REVIEWS]
    safe = sanitize_reviews(reviews)
    per_review: dict[str, SentimentResult] = {}
    for start in range(0, len(safe), SENTIMENT_BATCH_SIZE):
        originals = reviews[start : start + SENTIMENT_BATCH_SIZE]
        cleaned = safe[start : start + SENTIMENT_BATCH_SIZE]
        results = await _score_chunk(llm, cleaned)
        for original, result in zip(originals, results, strict=True):
            per_review[original.id] = result
    insights = await llm.generate_insights(safe)
    logger.info("Analyzed %d reviews", len(per_review))
    return ReviewAnalysis(reviews=reviews, per_review=per_review, insights=insights)
