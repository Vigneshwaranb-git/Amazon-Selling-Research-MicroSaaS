"""Tiny Amazon-Reviews-2023-shaped fixtures (no network) and a helper that imports them."""

import gzip
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.data.import_amazon_2023 import run_import

AS_OF = datetime(2023, 9, 30, tzinfo=UTC)


def ms(days_before_end: int) -> int:
    """Review timestamp in milliseconds, N days before the dataset end."""
    return int((AS_OF - timedelta(days=days_before_end)).timestamp() * 1000)


def _meta(asin: str, **kw: Any) -> dict[str, Any]:
    rec: dict[str, Any] = {
        "parent_asin": asin,
        "title": f"Product {asin}",
        "main_category": "Appliances",
        "average_rating": 4.4,
        "rating_number": 120,
        "price": 25.5,
        "images": [{"large": f"https://img.example/{asin}.jpg", "variant": "MAIN"}],
        "categories": ["Appliances", "Ice Makers"],
        "details": {"Best Sellers Rank": {"Appliances": 100, "Ice Makers": 5}, "Brand": "Acme"},
        "store": "Acme Store",
    }
    rec.update(kw)
    return rec


def meta_lines() -> list[str]:
    ranges_rank = "1,234 in Appliances (See Top 100 in Appliances) #7 in Ranges"
    rows: list[Any] = [
        _meta("B000000001"),
        _meta(
            "B000000002",
            price="$1,299.00",
            details={"Best Sellers Rank": ranges_rank},
            categories=["Appliances", "Ranges"],
        ),
        _meta("B000000003", price=None),  # no price
        _meta("B000000004", details={"Brand": "NoRank"}),  # no rank
        _meta("B000000005", price=None, details={}),  # neither
        _meta("B000000006", details={"Best Sellers Rank": "{'Appliances': 50}"}, price="from 9.5"),
        _meta("B000000001"),  # duplicate parent_asin
        _meta("short"),  # invalid ASIN
        _meta(
            "B000000007",
            details={"Best Sellers Rank": {"Tools & Home Improvement": 9, "Appliances": 30000}},
        ),
        ["not", "a", "dict"],
    ]
    lines = [json.dumps(r) for r in rows]
    lines.insert(3, "{this is not json")
    return lines


def _review(asin: str, rating: float, ts: int, user: str, text: str) -> dict[str, Any]:
    return {
        "parent_asin": asin,
        "rating": rating,
        "title": f"T {user}",
        "text": text,
        "timestamp": ts,
        "user_id": user,
        "verified_purchase": True,
    }


def review_lines() -> list[str]:
    rows: list[Any] = []
    # B000000001: 12 reviews in the last 12 months, 4 in the prior 12 months, 1 earlier.
    for i in range(12):
        text = f"Great item {i}<br />ok"
        rows.append(_review("B000000001", 5 if i % 3 else 1, ms(10 + i * 20), f"u{i}", text))
    for i in range(4):
        rows.append(_review("B000000001", 4, ms(400 + i * 30), f"p{i}", f"Fine {i}"))
    rows.append(_review("B000000001", 2, ms(1000), "old", "Old broke"))
    rows.append(_review("B000000002", 3, ms(5), "x", "ok"))
    rows.append(_review("B999999999", 5, ms(5), "y", "not kept"))  # other product
    rows.append(_review("B000000001", 9, ms(5), "bad", "rating out of range"))
    rows.append({"parent_asin": "B000000001", "rating": 5.0, "text": "no timestamp"})
    lines = [json.dumps(r) for r in rows]
    lines.insert(2, "garbage line")
    return lines


def write_fixtures(tmp: Path) -> tuple[Path, Path]:
    meta = tmp / "meta_Appliances.jsonl.gz"
    reviews = tmp / "Appliances.jsonl.gz"
    with gzip.open(meta, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(meta_lines()) + "\n")
    with gzip.open(reviews, "wt", encoding="utf-8") as fh:
        fh.write("\n".join(review_lines()) + "\n")
    return meta, reviews


def build_dataset(tmp: Path, **kwargs: Any) -> Path:
    """Import the fixtures into ``tmp/ds.sqlite`` and return its path."""
    meta, reviews = write_fixtures(tmp)
    out = tmp / "ds.sqlite"
    params: dict[str, Any] = {
        "category": "Appliances",
        "out": out,
        "max_products": 100,
        "max_reviews_per_product": 50,
        "max_review_lines": None,
        "meta_source": str(meta),
        "reviews_source": str(reviews),
    }
    params.update(kwargs)
    run_import(**params)
    return out
