"""Gap-filling tests: Dodo HTTP client, signature verification, mock providers."""

import asyncio
import base64
import json
import time
from typing import Any

import httpx
import pytest

from app.config import settings
from app.services import dodo_client as dc
from app.services.providers import (
    MockLLMProvider,
    MockProductDataProvider,
    get_llm_provider,
    get_product_data_provider,
)
from app.services.providers.base import Review


def run(coro: Any) -> Any:
    return asyncio.run(coro)


# ---------------------------------------------------------------- dodo client
def _patch_httpx(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    seen: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    real = httpx.AsyncClient

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(wrapped)
        return real(*args, **kwargs)

    monkeypatch.setattr(dc.httpx, "AsyncClient", factory)
    return seen


def _checkout(client: dc.HttpxDodoClient, name: str | None = None) -> Any:
    return run(
        client.create_checkout(
            product_id="prod_1",
            email="a@b.co",
            name=name,
            return_url="https://app/x",
            metadata={"user_id": "1"},
        )
    )


def test_httpx_client_success_builds_request(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_httpx(monkeypatch, lambda r: httpx.Response(200, json={"checkout_url": "u"}))
    out = _checkout(dc.HttpxDodoClient("key", "https://dodo.test/"))
    assert out == {"checkout_url": "u"}
    req = seen[0]
    assert str(req.url) == "https://dodo.test/checkouts"  # trailing slash stripped
    assert req.headers["authorization"] == "Bearer key"
    body = json.loads(req.content)
    assert body["product_cart"] == [{"product_id": "prod_1", "quantity": 1}]
    assert "billing_address" not in body and "billing" not in body
    assert body["customer"] == {"email": "a@b.co", "name": "a@b.co"}  # name falls back to email
    assert body["metadata"] == {"user_id": "1"}


def test_httpx_client_sends_billing_country_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_httpx(monkeypatch, lambda r: httpx.Response(200, json={}))
    run(
        dc.HttpxDodoClient("k", "https://d").create_checkout(
            product_id="p",
            email="a@b.co",
            name=None,
            return_url="https://app/x",
            metadata={},
            billing_country="GB",
        )
    )
    assert json.loads(seen[0].content)["billing_address"] == {"country": "GB"}


def test_httpx_client_uses_name_when_given(monkeypatch: pytest.MonkeyPatch) -> None:
    seen = _patch_httpx(monkeypatch, lambda r: httpx.Response(200, json={}))
    _checkout(dc.HttpxDodoClient("k", "https://d"), name="Jane")
    assert json.loads(seen[0].content)["customer"]["name"] == "Jane"


def test_httpx_client_http_error_raises_dodo_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, lambda r: httpx.Response(500, json={"e": 1}))
    with pytest.raises(dc.DodoError):
        _checkout(dc.HttpxDodoClient("k", "https://d"))


def test_httpx_client_invalid_json_raises_dodo_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_httpx(monkeypatch, lambda r: httpx.Response(200, content=b"<html>"))
    with pytest.raises(dc.DodoError):
        _checkout(dc.HttpxDodoClient("k", "https://d"))


def test_httpx_client_network_error_raises_dodo_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _patch_httpx(monkeypatch, boom)
    with pytest.raises(dc.DodoError):
        _checkout(dc.HttpxDodoClient("k", "https://d"))


def test_whsec_secret_is_base64_decoded() -> None:
    raw = b"super-secret-bytes"
    secret = "whsec_" + base64.b64encode(raw).decode()
    sig = dc.compute_signature(secret, "id", "1", b"{}")
    assert sig == dc.compute_signature(raw.decode(), "id", "1", b"{}")


def test_whsec_invalid_base64_falls_back_to_literal() -> None:
    secret = "whsec_!!!not-base64!!!"
    assert dc._secret_bytes(secret) == secret.encode()


def _sig(secret: str, body: bytes, ts: int, wid: str = "m") -> str:
    return "v1," + dc.compute_signature(secret, wid, str(ts), body)


def test_verify_webhook_error_branches() -> None:
    now = 1_000_000.0
    body = b"{}"
    ok = _sig("s", body, int(now))
    dc.verify_webhook(
        secret="s", webhook_id="m", timestamp=str(int(now)), signature_header=ok, body=body, now=now
    )
    with pytest.raises(dc.InvalidSignatureError, match="not configured"):
        dc.verify_webhook(
            secret="", webhook_id="m", timestamp="1", signature_header=ok, body=body, now=now
        )
    with pytest.raises(dc.InvalidSignatureError, match="Invalid timestamp"):
        dc.verify_webhook(
            secret="s", webhook_id="m", timestamp="abc", signature_header=ok, body=body, now=now
        )
    # tolerance boundary: exactly 300s ok, 301s rejected, future also rejected
    for delta, valid in ((300, True), (301, False), (-301, False)):
        ts = int(now) - delta
        kwargs: dict[str, Any] = {
            "secret": "s",
            "webhook_id": "m",
            "timestamp": str(ts),
            "signature_header": _sig("s", body, ts),
            "body": body,
            "now": now,
        }
        if valid:
            dc.verify_webhook(**kwargs)
        else:
            with pytest.raises(dc.InvalidSignatureError, match="tolerance"):
                dc.verify_webhook(**kwargs)


def test_verify_webhook_rejects_wrong_version_and_garbage() -> None:
    body = b"x"
    good = dc.compute_signature("s", "m", "5000", body)
    for header in (f"v2,{good}", good, "v1,", "garbage,more"):
        with pytest.raises(dc.InvalidSignatureError, match="mismatch"):
            dc.verify_webhook(
                secret="s",
                webhook_id="m",
                timestamp="5000",
                signature_header=header,
                body=body,
                now=5000.0,
            )


def test_verify_webhook_uses_wall_clock_by_default() -> None:
    ts = int(time.time())
    dc.verify_webhook(
        secret="s",
        webhook_id="m",
        timestamp=str(ts),
        signature_header=_sig("s", b"b", ts),
        body=b"b",
    )


def test_get_dodo_client_factory() -> None:
    from app.routers.billing import get_dodo_client

    assert isinstance(get_dodo_client(), dc.HttpxDodoClient)


# -------------------------------------------------------------- mock providers
def test_provider_factories_return_mocks_even_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    assert isinstance(get_product_data_provider(), MockProductDataProvider)
    assert isinstance(get_llm_provider(), MockLLMProvider)
    monkeypatch.setattr(settings, "AMAZON_DATA_API_KEY", "k")
    monkeypatch.setattr(settings, "LLM_API_KEY", "k")
    assert isinstance(get_product_data_provider(), MockProductDataProvider)
    assert isinstance(get_llm_provider(), MockLLMProvider)


def test_mock_get_product_validation_and_determinism() -> None:
    p = MockProductDataProvider()
    assert run(p.get_product("")) is None
    assert run(p.get_product("short")) is None
    assert run(p.get_product("B" * 11)) is None
    a = run(p.get_product("B012345678"))
    assert a is not None
    assert a == run(p.get_product("B012345678"))
    assert a.price > 0 and a.bsr >= 1000 and 3.5 <= a.rating <= 5.0
    assert run(p.get_product("B012345679")) != a


def test_mock_search_products() -> None:
    p = MockProductDataProvider()
    res = run(p.search_products("yoga mat", category="Pets", limit=3))
    assert len(res) == 3
    assert all(r.category == "Pets" for r in res)
    assert res[0].title == "Yoga Mat #1"
    assert all(len(r.asin) == 10 and r.asin.startswith("B") for r in res)
    assert res == run(p.search_products("yoga mat", category="Pets", limit=3))
    assert run(p.search_products("x", limit=0)) == []


def test_mock_bsr_history() -> None:
    p = MockProductDataProvider()
    pts = run(p.get_bsr_history("B012345678", days=10))
    assert len(pts) == 10
    assert [x.day for x in pts] == sorted(x.day for x in pts)
    assert all(x.bsr >= 1 for x in pts)
    assert pts == run(p.get_bsr_history("B012345678", days=10))
    assert run(p.get_bsr_history("B012345678", days=0)) == []


def test_mock_reviews_shape() -> None:
    p = MockProductDataProvider()
    revs = run(p.get_reviews("B012345678", limit=20))
    assert len(revs) == 20
    assert {r.id for r in revs} == {f"B012345678-{i}" for i in range(20)}
    assert all(1 <= r.rating <= 5 for r in revs)
    for r in revs:
        if r.rating >= 4:
            assert "Great" in r.body
        else:
            assert r.body.startswith("Disappointed")


def _rev(rating: int, body: str) -> Review:
    return Review(id=str(rating), rating=rating, title="t", body=body)


def test_mock_llm_sentiment_labels() -> None:
    llm = MockLLMProvider()
    empty = run(llm.analyze_sentiment([]))
    assert (empty.score, empty.label) == (0.0, "neutral")
    pos = run(llm.analyze_sentiment([_rev(5, "Great, love it. Perfect!")]))
    assert pos.label == "positive" and pos.score > 0.2
    neg = run(llm.analyze_sentiment([_rev(1, "terrible. poor. broke.")]))
    assert neg.label == "negative" and neg.score == -1.0  # clamped
    neu = run(llm.analyze_sentiment([_rev(3, "it arrived on tuesday")]))
    assert neu.label == "neutral" and neu.score == 0.0


def test_mock_llm_pain_points_and_summarize() -> None:
    llm = MockLLMProvider()
    reviews = [
        _rev(1, "Disappointed, poor durability."),
        _rev(2, "Disappointed, poor durability."),
        _rev(1, "Disappointed, battery life."),
        _rev(5, "poor durability but great"),  # rating > 2 ignored
    ]
    pts = run(llm.extract_pain_points(reviews))
    assert pts == ["poor durability", "battery life"]
    assert run(llm.extract_pain_points(reviews, limit=1)) == ["poor durability"]
    assert run(llm.extract_pain_points([])) == []
    result = run(llm.analyze_sentiment(reviews))
    assert result.pain_points == pts
    assert run(llm.summarize("a b c d e", max_words=3)) == "a b c"
    assert run(llm.summarize("")) == ""
