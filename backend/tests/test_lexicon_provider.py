"""LexiconLLMProvider: rule-based sentiment, pain points and templated insights."""

import asyncio

import pytest

from app.services.providers import lexicon as lx
from app.services.providers.base import Review
from app.services.providers.lexicon import LexiconLLMProvider
from app.services.sentiment_service import analyze_reviews


def _r(rating: int, body: str, title: str = "", rid: str = "1") -> Review:
    return Review(id=rid, rating=rating, title=title, body=body)


def test_review_score_blends_stars_and_text() -> None:
    assert lx.review_score(_r(5, "Great, love it")) == 1.0
    assert lx.review_score(_r(1, "Terrible, it broke")) == -1.0
    assert lx.review_score(_r(3, "ordinary")) == 0.0  # no lexicon hit -> stars only
    assert lx.review_score(_r(5, "nothing special")) == 1.0
    # Negation flips polarity: "not good" is negative even at 3 stars.
    assert lx.review_score(_r(3, "not good")) < 0
    assert lx.review_score(_r(3, "never disappointed")) > 0
    # Out-of-range ratings are clamped.
    assert lx.review_score(_r(9, "")) == 1.0


def test_pain_points_only_for_low_ratings_and_respect_negation() -> None:
    assert lx.review_pain_points(_r(1, "It broke after a week and leaks, cheap material")) == [
        "breaks easily",
        "cheap material",
        "leaks",
    ]
    assert lx.review_pain_points(_r(5, "it broke")) == []  # praise reviews are not mined
    assert lx.review_pain_points(_r(2, "it didn't leak and never broke")) == []
    assert lx.review_pain_points(_r(2, "doesn't work, too small, smells awful")) == [
        "stopped working",
        "too small",
        "bad smell",
    ]
    assert lx.review_pain_points(_r(1, "STOPPED WORKING!!", title="Junk")) == ["stopped working"]
    assert lx.review_pain_points(_r(1, "")) == []


def test_praise_detection() -> None:
    found = lx.review_praise(_r(5, "Easy to use and works great, very sturdy"))
    assert set(found) == {"easy to use", "sturdy and durable", "works well"}
    assert lx.review_praise(_r(2, "easy to use")) == []


def test_analyze_sentiment_and_batch() -> None:
    llm = LexiconLLMProvider()
    reviews = [_r(5, "Great product, love it", rid="a"), _r(1, "Broke, terrible", rid="b")]
    batch = asyncio.run(llm.analyze_sentiment_batch(reviews))
    assert [b.label for b in batch] == ["positive", "negative"]
    assert batch[1].pain_points == ["breaks easily"]
    agg = asyncio.run(llm.analyze_sentiment(reviews))
    assert agg.label == "neutral" and agg.pain_points == ["breaks easily"]
    empty = asyncio.run(llm.analyze_sentiment([]))
    assert (empty.score, empty.label) == (0.0, "neutral")
    assert asyncio.run(llm.analyze_sentiment_batch([])) == []


def test_extract_pain_points_ranked_and_limited() -> None:
    llm = LexiconLLMProvider()
    reviews = [
        _r(1, "leaks"),
        _r(2, "it leaks and is too small"),
        _r(1, "flimsy and too small and noisy"),
        _r(1, "leaking"),
    ]
    assert asyncio.run(llm.extract_pain_points(reviews, limit=2)) == ["leaks", "too small"]
    assert asyncio.run(llm.extract_pain_points([_r(5, "leaks")])) == []


def test_generate_insights_uses_real_counts() -> None:
    llm = LexiconLLMProvider()
    reviews = (
        [_r(5, "easy to use, works great")] * 3
        + [_r(4, "easy to use")]
        + [_r(1, "it broke")] * 2
        + [_r(2, "stopped working")]
    )
    ins = asyncio.run(llm.generate_insights(reviews))
    assert ins.pros[0] == "Easy to use: praised in 4 of 4 positive reviews"
    assert "Works well: praised in 3 of 4 positive reviews" in ins.pros
    assert ins.cons[0] == "Breaks easily: mentioned in 2 of 3 critical reviews"
    assert ins.cons[1] == "Stopped working: mentioned in 1 of 3 critical reviews"
    assert (
        ins.opportunities[0]
        == "Improve durability and build quality (2 complaints about 'breaks easily')"
    )
    assert "1 complaint about 'stopped working'" in ins.opportunities[1]


def test_generate_insights_fallbacks_never_invent() -> None:
    llm = LexiconLLMProvider()
    assert asyncio.run(llm.generate_insights([])).pros == []
    only_stars = asyncio.run(llm.generate_insights([_r(5, "fine"), _r(1, "meh")]))
    assert only_stars.pros == ["1 of 2 reviews are rated 4-5 stars"]
    assert only_stars.cons == ["1 of 2 reviews are rated 3 stars or lower"]
    assert only_stars.opportunities == []


def test_summarize_is_extractive() -> None:
    llm = LexiconLLMProvider()
    assert asyncio.run(llm.summarize("one  two three four", max_words=2)) == "one two"


def test_pipeline_keeps_pii_scrubbing_and_batching() -> None:
    calls: list[int] = []

    class Spy(LexiconLLMProvider):
        async def analyze_sentiment_batch(self, reviews: list[Review]):  # type: ignore[no-untyped-def]
            calls.append(len(reviews))
            for review in reviews:
                assert "@" not in review.body and "http" not in review.body
            return await super().analyze_sentiment_batch(reviews)

    reviews = [
        _r(1, f"it broke, mail me bob@example.com http://spam.example {i}", rid=f"id{i}")
        for i in range(45)
    ]
    result = asyncio.run(analyze_reviews(Spy(), reviews))
    assert calls == [20, 20, 5]  # batched, not one call per review
    assert len(result.per_review) == 45
    assert result.per_review["id0"].pain_points == ["breaks easily"]
    assert result.insights.cons


@pytest.mark.parametrize("score", [-0.5, 0.0, 0.5])
def test_label_thresholds(score: float) -> None:
    expected = {-0.5: "negative", 0.0: "neutral", 0.5: "positive"}[score]
    assert lx._label(score) == expected
