"""Tests for review & sentiment endpoints."""

import asyncio
from collections.abc import Iterator
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.main import app
from app.models.product import Product
from app.models.review_log import ReviewLog
from app.models.user import User
from app.rate_limit import limiter
from app.services.providers.base import LLMProvider, Review, SentimentResult
from app.services.providers.mock import MockLLMProvider, MockProductDataProvider
from app.services.sentiment_service import MAX_REVIEW_CHARS, analyze_reviews, sanitize_reviews

ASIN = "B012345678"
BASE = "/api/v1/reviews"


@pytest.fixture
def user(db_session: Session) -> Iterator[User]:
    u = User(id=1, email="a@example.com")
    db_session.add(u)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


def _analyze(client: TestClient, asin: str = ASIN) -> dict:  # type: ignore[type-arg]
    r = client.post(f"{BASE}/{asin}/analyze")
    assert r.status_code == 200, r.text
    return r.json()  # type: ignore[no-any-return]


def test_requires_auth(client: TestClient) -> None:
    assert client.get(f"{BASE}/{ASIN}").status_code == 401
    assert client.post(f"{BASE}/{ASIN}/analyze").status_code == 401
    assert client.get(f"{BASE}/{ASIN}/summary").status_code == 401
    assert client.get(f"{BASE}/{ASIN}/pain-points").status_code == 401


def test_unknown_product_and_bad_asin(client: TestClient, user: User) -> None:
    r = client.get(f"{BASE}/{ASIN}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert client.get(f"{BASE}/{ASIN}/pain-points").status_code == 404
    assert client.get(f"{BASE}/bad").status_code == 422


def test_list_empty_when_not_analyzed(client: TestClient, user: User, db_session: Session) -> None:
    db_session.add(Product(asin=ASIN, title="P"))
    db_session.commit()
    r = client.get(f"{BASE}/{ASIN}")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_analyze_and_filters(client: TestClient, user: User) -> None:
    data = _analyze(client)
    assert data["analyzed"] == 50
    assert data["summary"]["asin"] == ASIN
    body = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()
    assert body["total"] == 50
    item = body["items"][0]
    assert set(item) == {
        "review_id",
        "rating",
        "review_text",
        "sentiment_score",
        "sentiment_label",
        "pain_points",
        "reviewed_at",
    }

    r1 = client.get(f"{BASE}/{ASIN}", params={"rating": 1, "page_size": 100}).json()
    assert r1["items"] and all(i["rating"] == 1 for i in r1["items"])
    assert client.get(f"{BASE}/{ASIN}", params={"rating": 6}).status_code == 422

    kw = client.get(f"{BASE}/{ASIN}", params={"keyword": "GREAT VALUE", "page_size": 100}).json()
    assert kw["items"] and all("great value" in i["review_text"].lower() for i in kw["items"])
    # LIKE wildcards are literal
    assert client.get(f"{BASE}/{ASIN}", params={"keyword": "%"}).json()["total"] == 0
    assert client.get(f"{BASE}/{ASIN}", params={"keyword": "_"}).json()["total"] == 0

    page = client.get(f"{BASE}/{ASIN}", params={"page_size": 10, "page": 2}).json()
    assert len(page["items"]) == 10 and page["page"] == 2
    assert client.get(f"{BASE}/{ASIN}", params={"page_size": 101}).status_code == 422


def test_reanalyze_is_idempotent(client: TestClient, user: User, db_session: Session) -> None:
    _analyze(client)
    first = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()
    _analyze(client)
    second = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()
    assert first["total"] == second["total"] == 50
    assert first["items"] == second["items"]
    assert db_session.execute(select(func.count(ReviewLog.id))).scalar_one() == 50


def test_summary_404_then_200(client: TestClient, user: User, db_session: Session) -> None:
    db_session.add(Product(asin=ASIN, title="P"))
    db_session.commit()
    r = client.get(f"{BASE}/{ASIN}/summary")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    _analyze(client)
    r = client.get(f"{BASE}/{ASIN}/summary")
    assert r.status_code == 200
    body = r.json()
    assert body["asin"] == ASIN
    assert body["pros"] and body["cons"] and body["opportunities"]
    assert body["generated_at"]


def test_pain_point_aggregation(client: TestClient, user: User) -> None:
    _analyze(client)
    reviews = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()["items"]
    expected: dict[str, int] = {}
    for rv in reviews:
        for p in rv["pain_points"]:
            expected[p] = expected.get(p, 0) + 1
    body = client.get(f"{BASE}/{ASIN}/pain-points").json()
    assert body["asin"] == ASIN
    items = body["items"]
    assert items
    assert {i["label"]: i["count"] for i in items} == expected
    counts = [i["count"] for i in items]
    assert counts == sorted(counts, reverse=True)
    assert abs(sum(i["share_pct"] for i in items) - 100) < 0.5
    assert all(i["example"] for i in items)


def test_sanitize_strips_pii_and_truncates() -> None:
    r = Review(
        id="secret-id",
        rating=1,
        title="mail me bob@example.com",
        body="call +1 (555) 123-4567 or see https://x.io/p " + "a" * 5000,
    )
    [clean] = sanitize_reviews([r])
    assert clean.id == "0"
    assert "bob@example.com" not in clean.title
    assert "555" not in clean.body and "https://" not in clean.body
    assert len(clean.body) <= MAX_REVIEW_CHARS


def test_provider_receives_sanitized_text(client: TestClient, user: User) -> None:
    seen: list[str] = []
    original = MockLLMProvider.analyze_sentiment_batch

    async def spy(self: MockLLMProvider, reviews: list[Review]):  # type: ignore[no-untyped-def]
        seen.extend(r.id for r in reviews)
        return await original(self, reviews)

    MockLLMProvider.analyze_sentiment_batch = spy  # type: ignore[method-assign,assignment]
    try:
        _analyze(client)
    finally:
        MockLLMProvider.analyze_sentiment_batch = original  # type: ignore[method-assign]
    assert len(seen) == 50 and all(i.isdigit() for i in seen)


def test_sentiment_is_batched(
    client: TestClient, user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    batches: list[int] = []
    singles: list[int] = []
    batch_orig = MockLLMProvider.analyze_sentiment_batch
    single_orig = MockLLMProvider.analyze_sentiment

    async def spy_batch(self: MockLLMProvider, reviews: list[Review]):  # type: ignore[no-untyped-def]
        batches.append(len(reviews))
        return await batch_orig(self, reviews)

    async def spy_single(self: MockLLMProvider, reviews: list[Review]):  # type: ignore[no-untyped-def]
        singles.append(len(reviews))
        return await single_orig(self, reviews)

    monkeypatch.setattr(MockLLMProvider, "analyze_sentiment_batch", spy_batch)
    monkeypatch.setattr(MockLLMProvider, "analyze_sentiment", spy_single)
    _analyze(client)
    assert batches == [20, 20, 10]  # 50 reviews -> 3 provider calls, not 50
    assert singles == []


def test_batch_matches_per_review_results() -> None:
    llm = MockLLMProvider()
    revs = asyncio.run(MockProductDataProvider().get_reviews(ASIN, limit=30))
    batched = asyncio.run(llm.analyze_sentiment_batch(revs))
    single = [asyncio.run(llm.analyze_sentiment([r])) for r in revs]
    assert batched == single


@pytest.mark.parametrize("mode", ["raise", "short"])
def test_batch_failure_falls_back_per_review(mode: str, monkeypatch: pytest.MonkeyPatch) -> None:
    llm = MockLLMProvider()
    revs = asyncio.run(MockProductDataProvider().get_reviews(ASIN, limit=25))
    expected = asyncio.run(analyze_reviews(MockLLMProvider(), revs))
    singles: list[int] = []
    single_orig = MockLLMProvider.analyze_sentiment

    async def bad_batch(reviews: list[Review]) -> list[SentimentResult]:
        if mode == "raise":
            raise RuntimeError("provider down")
        return []

    async def spy_single(self: MockLLMProvider, reviews: list[Review]) -> SentimentResult:
        singles.append(len(reviews))
        return await single_orig(self, reviews)

    monkeypatch.setattr(llm, "analyze_sentiment_batch", bad_batch)
    monkeypatch.setattr(MockLLMProvider, "analyze_sentiment", spy_single)
    got = asyncio.run(analyze_reviews(llm, revs))
    assert got.per_review == expected.per_review
    assert len(singles) == 25  # every chunk fell back to one call per review


def test_base_provider_default_batch_calls_per_review() -> None:
    calls: list[int] = []

    class Single(MockLLMProvider):
        analyze_sentiment_batch = LLMProvider.analyze_sentiment_batch  # type: ignore[assignment]

        async def analyze_sentiment(self, reviews: list[Review]) -> SentimentResult:
            calls.append(len(reviews))
            return SentimentResult(score=0.0, label="neutral")

    revs = [Review(id=str(i), rating=3, title="t", body="b") for i in range(3)]
    out = asyncio.run(Single().analyze_sentiment_batch(revs))
    assert len(out) == 3 and calls == [1, 1, 1]


def test_reviewed_at_persisted_and_returned(
    client: TestClient, user: User, db_session: Session
) -> None:
    _analyze(client)
    items = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()["items"]
    assert len(items) == 50
    stamps = [i["reviewed_at"] for i in items]
    assert all(isinstance(x, str) for x in stamps)
    parsed = [datetime.fromisoformat(x) for x in stamps]
    assert parsed == sorted(parsed, reverse=True)  # mock reviews are newest-first
    assert len({p.date() for p in parsed}) == 50
    assert (
        db_session.execute(
            select(func.count(ReviewLog.id)).where(ReviewLog.reviewed_at.is_(None))
        ).scalar_one()
        == 0
    )
    # Deterministic and stable across re-analysis.
    _analyze(client)
    again = client.get(f"{BASE}/{ASIN}", params={"page_size": 100}).json()["items"]
    assert [i["reviewed_at"] for i in again] == stamps


def test_mock_review_dates_deterministic() -> None:
    p = MockProductDataProvider()
    a = asyncio.run(p.get_reviews(ASIN, limit=10))
    b = asyncio.run(p.get_reviews(ASIN, limit=10))
    assert [r.reviewed_at for r in a] == [r.reviewed_at for r in b]
    assert all(isinstance(r.reviewed_at, date) for r in a)


def test_analyze_rate_limited(client: TestClient, user: User) -> None:
    limiter.enabled = True
    limiter.reset()
    try:
        codes = [client.post(f"{BASE}/{ASIN}/analyze").status_code for _ in range(6)]
    finally:
        limiter.enabled = False
        limiter.reset()
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
