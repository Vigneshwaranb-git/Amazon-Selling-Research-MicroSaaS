"""DatasetProductDataProvider, snapshot-skip behaviour, config errors and /meta/data-source."""

import asyncio
import logging
import os
import sqlite3
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.data import schema
from app.dependencies import get_current_user
from app.main import app
from app.models.bsr_snapshot import BsrSnapshot
from app.models.product import Product
from app.models.user import User
from app.services import providers
from app.services.providers import (
    DatasetConfigError,
    DatasetProductDataProvider,
    LexiconLLMProvider,
    MockProductDataProvider,
    get_llm_provider,
    get_product_data_provider,
)
from app.services.providers import dataset as ds
from app.services.snapshot_job import run_snapshot_job, upsert_product
from tests._dataset import build_dataset

BASE = "/api/v1/products"
ASIN = "B000000001"


@pytest.fixture(scope="module")
def dataset_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_dataset(tmp_path_factory.mktemp("dataset"))


@pytest.fixture
def provider(dataset_path: Path) -> DatasetProductDataProvider:
    return DatasetProductDataProvider(dataset_path)


@pytest.fixture
def use_dataset(dataset_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(settings, "DATA_PROVIDER", "dataset")
    monkeypatch.setattr(settings, "DATASET_PATH", str(dataset_path))
    monkeypatch.setattr(providers, "_dataset_provider", None)
    return dataset_path


@pytest.fixture
def user(db_session: Session) -> Iterator[User]:
    u = User(id=1, email="a@example.com")
    db_session.add(u)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: u
    yield u
    app.dependency_overrides.pop(get_current_user, None)


# ----------------------------------------------------------------------------- formulas
def test_sales_estimate_formula_is_capped_and_monotonic() -> None:
    at_200 = round(30 * 99_340 / 200**0.93)
    assert ds.estimate_monthly_sales_from_bsr(200) == at_200
    assert ds.estimate_monthly_sales_from_bsr(1) == at_200  # fit invalid above rank ~200: capped
    assert ds.estimate_monthly_sales_from_bsr(0) == at_200
    assert ds.estimate_monthly_sales_from_bsr(1_000) == round(30 * 99_340 / 1_000**0.93)
    assert ds.estimate_monthly_sales_from_bsr(1_000) > ds.estimate_monthly_sales_from_bsr(50_000)
    assert ds.estimate_monthly_sales_from_bsr(10**12) == 1


def test_compute_trend() -> None:
    assert ds.compute_trend(0, 0, None, None) == 50
    assert ds.compute_trend(5, 4, None, None) == 50  # < 10 reviews: not enough evidence
    assert ds.compute_trend(20, 20, None, None) == 50
    assert ds.compute_trend(20, 0, None, None) == 90
    assert ds.compute_trend(0, 20, None, None) == 10
    assert ds.compute_trend(20, 20, 4.5, 4.0) == 51  # +0.5 star -> +1.25
    assert ds.compute_trend(20, 20, 1.0, 5.0) == 40  # rating drop capped at -10
    assert ds.compute_trend(20, 0, 5.0, None) == 90  # rating needs both windows


def test_compute_saturation_bounds_and_direction() -> None:
    low = ds.compute_saturation(0, 0.0, 10**6, 1)
    high = ds.compute_saturation(100_000, 5.0, 1, 100_000)
    assert 0 <= low < high <= 100
    assert high == 100
    assert ds.compute_saturation(50, 4.0, 5000, 100) < ds.compute_saturation(5000, 4.0, 5000, 100)
    assert ds.compute_saturation(50, 4.0, 5000, 10) < ds.compute_saturation(50, 4.0, 5000, 3000)


# ----------------------------------------------------------------------------- provider
def test_get_product_is_honest_about_the_snapshot(provider: DatasetProductDataProvider) -> None:
    p = asyncio.run(provider.get_product(ASIN))
    assert p is not None
    assert (p.bsr, p.price, p.brand, p.category) == (100, Decimal("25.50"), "Acme", "Ice Makers")
    assert p.data_as_of == date(2023, 9, 30)
    assert p.monthly_sales_estimate == ds.estimate_monthly_sales_from_bsr(100)
    assert p.seller_count == 0  # unknown, not fabricated
    assert p.image_url.startswith("https://img.example/")
    assert p.trend_score is not None and 70 <= p.trend_score <= 80  # 12 vs 4 reviews
    assert p.saturation_score is not None and 0 <= p.saturation_score <= 100
    assert asyncio.run(provider.get_product("B0NOPE0000")) is None
    assert provider.supports_live_snapshots is False


def test_search_filters_orders_and_escapes(provider: DatasetProductDataProvider) -> None:
    everything = asyncio.run(provider.search_products(""))
    assert [p.bsr for p in everything] == sorted(p.bsr for p in everything)
    assert len(everything) == 4
    assert len(asyncio.run(provider.search_products("", limit=2))) == 2
    assert [p.asin for p in asyncio.run(provider.search_products("B000000002"))] == ["B000000002"]
    assert [p.asin for p in asyncio.run(provider.search_products("acme"))]  # brand match
    ranges = asyncio.run(provider.search_products("", category="ranges"))
    assert [p.asin for p in ranges] == ["B000000002"]
    assert asyncio.run(provider.search_products("%")) == []  # wildcard is literal
    assert len(asyncio.run(provider.search_products("", limit=10_000))) == 4  # clamped


def test_history_is_a_single_dated_snapshot(provider: DatasetProductDataProvider) -> None:
    points = asyncio.run(provider.get_bsr_history(ASIN, days=90))
    assert len(points) == 1
    assert points[0].day == date(2023, 9, 30) and points[0].bsr == 100
    assert points[0].estimated_sales == ds.estimate_monthly_sales_from_bsr(100)
    assert asyncio.run(provider.get_bsr_history("B0NOPE0000")) == []


def test_reviews_newest_first_with_real_dates(provider: DatasetProductDataProvider) -> None:
    reviews = asyncio.run(provider.get_reviews(ASIN, limit=5))
    assert len(reviews) == 5
    dates = [r.reviewed_at for r in reviews]
    assert dates == sorted(dates, reverse=True)  # type: ignore[type-var]
    assert all(r.reviewed_at is not None and r.reviewed_at.year == 2023 for r in reviews)
    assert all(1 <= r.rating <= 5 and r.id.startswith(ASIN) for r in reviews)
    assert asyncio.run(provider.get_reviews(ASIN, limit=0)) == []
    assert asyncio.run(provider.get_reviews("B0NOPE0000")) == []


def test_seed_asins_top_by_bsr(provider: DatasetProductDataProvider) -> None:
    top = asyncio.run(provider.seed_asins(2))
    assert top == ["B000000006", "B000000001"]


def test_concurrent_use_is_safe(provider: DatasetProductDataProvider) -> None:
    async def many() -> list[object]:
        calls = [provider.get_product(ASIN) for _ in range(20)]
        calls += [provider.get_reviews(ASIN, 5) for _ in range(20)]
        return list(await asyncio.gather(*calls))

    results = asyncio.run(many())
    assert len(results) == 40 and all(results)


def test_connection_is_read_only(provider: DatasetProductDataProvider) -> None:
    conn = sqlite3.connect(provider._uri, uri=True)
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM products")
    conn.close()


def test_notes_flag_truncated_reviews(tmp_path: Path) -> None:
    path = build_dataset(tmp_path, max_review_lines=3)
    notes = DatasetProductDataProvider(path).data_source_notes()
    assert any("partial" in n for n in notes)


# ----------------------------------------------------------------------------- config errors
def test_missing_file_error_names_the_import_command(tmp_path: Path) -> None:
    with pytest.raises(DatasetConfigError) as exc:
        DatasetProductDataProvider(tmp_path / "nope.sqlite")
    assert exc.value.status_code == 503
    assert "python -m app.data.import_amazon_2023 --category Appliances" in exc.value.message
    assert "nope.sqlite" in exc.value.message and "does not exist" in exc.value.message


def test_corrupt_incompatible_and_empty_files(tmp_path: Path, dataset_path: Path) -> None:
    corrupt = tmp_path / "corrupt.sqlite"
    corrupt.write_bytes(b"this is not a sqlite database" * 20)
    with pytest.raises(DatasetConfigError, match="not a valid dataset"):
        DatasetProductDataProvider(corrupt)

    wrong = tmp_path / "wrong.sqlite"
    con = sqlite3.connect(wrong)
    con.execute("CREATE TABLE other (x)")
    con.commit()
    con.close()
    with pytest.raises(DatasetConfigError, match="not a valid dataset"):
        DatasetProductDataProvider(wrong)

    old = tmp_path / "old.sqlite"
    old.write_bytes(dataset_path.read_bytes())
    con = sqlite3.connect(old)
    con.execute("UPDATE meta SET value='0' WHERE key='schema_version'")
    con.commit()
    con.close()
    with pytest.raises(DatasetConfigError, match="incompatible schema"):
        DatasetProductDataProvider(old)

    empty = tmp_path / "empty.sqlite"
    empty.write_bytes(dataset_path.read_bytes())
    con = sqlite3.connect(empty)
    con.execute("DELETE FROM products")
    con.commit()
    con.close()
    with pytest.raises(DatasetConfigError, match="no products"):
        DatasetProductDataProvider(empty)


def test_bad_as_of_falls_back_to_dataset_date(tmp_path: Path, dataset_path: Path) -> None:
    copy = tmp_path / "asof.sqlite"
    copy.write_bytes(dataset_path.read_bytes())
    con = sqlite3.connect(copy)
    con.execute("UPDATE meta SET value='garbage' WHERE key='data_as_of'")
    con.commit()
    con.close()
    assert DatasetProductDataProvider(copy).data_as_of == date.fromisoformat(schema.DATASET_AS_OF)


def test_factory_default_is_mock_and_dataset_never_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert isinstance(get_product_data_provider(), MockProductDataProvider)
    monkeypatch.setattr(settings, "DATA_PROVIDER", "dataset")
    monkeypatch.setattr(settings, "DATASET_PATH", str(tmp_path / "missing.sqlite"))
    monkeypatch.setattr(providers, "_dataset_provider", None)
    with pytest.raises(DatasetConfigError):
        get_product_data_provider()


def test_factory_caches_and_reloads_on_reimport(use_dataset: Path) -> None:
    first = get_product_data_provider()
    assert isinstance(first, DatasetProductDataProvider)
    assert get_product_data_provider() is first
    stat = use_dataset.stat()
    os.utime(use_dataset, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000_000))
    assert get_product_data_provider() is not first


def test_llm_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    assert not isinstance(get_llm_provider(), LexiconLLMProvider)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "lexicon")
    assert isinstance(get_llm_provider(), LexiconLLMProvider)


# ----------------------------------------------------------------------------- snapshot job
def test_seeding_and_detail_use_the_dataset(
    client: TestClient, user: User, use_dataset: Path, db_session: Session
) -> None:
    r = client.get(BASE, params={"page_size": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 4  # seeded from the dataset's top list, not mock keywords
    assert [i["asin"] for i in body["items"]][:2] == ["B000000006", "B000000001"]
    assert all(i["asin"].startswith("B00000000") for i in body["items"])

    d = client.get(f"{BASE}/{ASIN}").json()
    assert d["snapshot_count"] == 1  # the single real dataset snapshot, no backfilled series
    assert 70 <= d["trend_score"] <= 80
    h = client.get(f"{BASE}/{ASIN}/history").json()
    assert len(h["snapshots"]) == 1
    assert h["snapshots"][0]["captured_at"].startswith("2023-09-30")
    assert h["snapshots"][0]["bsr"] == 100


def test_snapshot_job_skips_static_dataset(
    client: TestClient,
    user: User,
    use_dataset: Path,
    db_session: Session,
    caplog: pytest.LogCaptureFixture,
) -> None:
    client.get(f"{BASE}/{ASIN}")
    client.get(f"{BASE}/B000000002")
    before = db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one()
    assert before == 2
    provider = get_product_data_provider()
    with caplog.at_level(logging.INFO, logger="app.services.snapshot_job"):
        refreshed = asyncio.run(run_snapshot_job(db_session, provider))
    assert refreshed == 0
    assert db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one() == before
    skipped = [r for r in caplog.records if "Snapshot job skipped" in r.getMessage()]
    assert len(skipped) == 1  # logged once per run, not per product

    # Re-upserting an existing product must not append either.
    asyncio.run(upsert_product(db_session, provider, ASIN))
    assert db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one() == before
    product = db_session.execute(select(Product).where(Product.asin == ASIN)).scalar_one()
    assert product.trend_score is not None and 70 <= product.trend_score <= 80


def test_snapshot_job_still_appends_for_live_providers(
    db_session: Session,
) -> None:
    mock = MockProductDataProvider()
    assert mock.supports_live_snapshots is True
    asyncio.run(upsert_product(db_session, mock, "B012345678"))
    n1 = db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one()
    assert asyncio.run(run_snapshot_job(db_session, mock)) == 1
    assert db_session.execute(select(func.count(BsrSnapshot.id))).scalar_one() == n1 + 1


def test_reviews_analyze_with_lexicon_on_real_reviews(
    client: TestClient,
    user: User,
    use_dataset: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "LLM_PROVIDER", "lexicon")
    r = client.post(f"/api/v1/reviews/{ASIN}/analyze")
    assert r.status_code == 200, r.text
    assert r.json()["analyzed"] == 17
    items = client.get(f"/api/v1/reviews/{ASIN}").json()["items"]
    assert items and all(i["reviewed_at"] for i in items)


# ----------------------------------------------------------------------------- meta endpoint
def test_meta_data_source_mock_is_public(client: TestClient) -> None:
    r = client.get("/api/v1/meta/data-source")  # no auth header
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "mock"
    assert body["attribution"] is None and body["data_as_of"] is None
    assert body["notes"] and all(isinstance(n, str) for n in body["notes"])


def test_meta_data_source_dataset(
    client: TestClient, use_dataset: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "LLM_PROVIDER", "lexicon")
    body = client.get("/api/v1/meta/data-source").json()
    assert body["provider"] == "dataset"
    assert body["attribution"] == schema.ATTRIBUTION
    assert body["data_as_of"] == "2023-09-30"
    joined = " ".join(body["notes"])
    assert "single snapshot from 2023-09-30" in joined
    assert "estimates" in joined and "licence" in joined and "lexicon" in joined


def test_meta_data_source_503_when_dataset_missing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(settings, "DATA_PROVIDER", "dataset")
    monkeypatch.setattr(settings, "DATASET_PATH", str(tmp_path / "missing.sqlite"))
    monkeypatch.setattr(providers, "_dataset_provider", None)
    r = client.get("/api/v1/meta/data-source")
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "DATA_PROVIDER_NOT_CONFIGURED"
    assert "python -m app.data.import_amazon_2023" in err["message"]
