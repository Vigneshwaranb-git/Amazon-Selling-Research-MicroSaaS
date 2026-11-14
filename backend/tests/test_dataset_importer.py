"""Importer parsing and end-to-end import of tiny fixtures (no network)."""

import gzip
import sqlite3
from decimal import Decimal
from pathlib import Path

import pytest

from app.data import import_amazon_2023 as imp
from app.data import schema
from tests._dataset import build_dataset, meta_lines, write_fixtures


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"Appliances": 1234}, [("Appliances", 1234)]),
        ('{"Appliances": 1234}', [("Appliances", 1234)]),
        ("{'Appliances': 12, 'Ice': '5,000'}", [("Appliances", 12), ("Ice", 5000)]),
        (
            "1,234 in Appliances (See Top 100 in Appliances) #5 in Ranges & Ovens",
            [("Appliances", 1234), ("Ranges & Ovens", 5)],
        ),
        ("#12 in Tools", [("Tools", 12)]),
        ({"A": 0, "B": "x", "C": True, "D": 7}, [("D", 7)]),
        ("{broken", []),
        ("", []),
        ("junk", []),
        (None, []),
        (42, []),
        (["list"], []),
    ],
)
def test_parse_rank(raw: object, expected: list[tuple[str, int]]) -> None:
    assert imp.parse_rank(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (12.5, Decimal("12.50")),
        (7, Decimal("7.00")),
        ("$1,299.00", Decimal("1299.00")),
        ("from 9.5", Decimal("9.50")),
        ("$10 - $20", Decimal("10.00")),
        ("None", None),
        ("", None),
        (None, None),
        (0, None),
        (-3.0, None),
        (float("nan"), None),
        (float("inf"), None),
        (True, None),
        ([1], None),
        (1e12, None),
    ],
)
def test_parse_price(raw: object, expected: Decimal | None) -> None:
    assert imp.parse_price(raw) == expected


def test_parse_timestamp() -> None:
    assert imp.parse_timestamp(1_600_000_000_000) == 1_600_000_000
    assert imp.parse_timestamp(1_600_000_000) == 1_600_000_000
    assert imp.parse_timestamp(0) is None
    assert imp.parse_timestamp("1") is None
    assert imp.parse_timestamp(True) is None


def test_build_product_reasons_and_headline_rank() -> None:
    base = {
        "parent_asin": "B000000001",
        "title": "  A   thing ",
        "price": 10,
        "details": {"Best Sellers Rank": {"Tools": 9, "Appliances": 300}},
        "images": {"large": ["https://x/y.jpg"]},
        "average_rating": "bad",
        "rating_number": None,
    }
    row, reason = imp.build_product(base, "Appliances")
    assert row is not None and reason == ""
    # The rank in the imported category beats the first listed one.
    assert (row.bsr, row.bsr_category) == (300, "Appliances")
    assert (row.bsr_sub, row.bsr_sub_category) == (9, "Tools")
    assert row.title == "A thing" and row.rating == 0.0 and row.review_count == 0
    assert row.image_url == "https://x/y.jpg" and row.category == "Appliances"
    assert imp.build_product("x", "A") == (None, "invalid")
    assert imp.build_product({**base, "parent_asin": "bad"}, "A")[1] == "invalid"
    assert imp.build_product({**base, "title": ""}, "A")[1] == "invalid"
    assert imp.build_product({**base, "price": None}, "A")[1] == "no_price"
    assert imp.build_product({**base, "details": "{}"}, "A")[1] == "no_rank"
    assert imp.build_product({**base, "price": None, "details": None}, "A")[1] == (
        "no_rank_no_price"
    )


def test_iter_gz_lines_plain_gz_and_truncated(tmp_path: Path) -> None:
    plain = tmp_path / "p.jsonl"
    plain.write_text('{"a":1}\n\n{"a":2}', encoding="utf-8")
    assert list(imp.iter_gz_lines(str(plain))) == [b'{"a":1}', b'{"a":2}']
    assert list(imp.iter_gz_lines(str(plain), max_lines=1)) == [b'{"a":1}']

    payload = b"".join(b'{"n": %d}\n' % i for i in range(5000))
    full = gzip.compress(payload)
    cut = tmp_path / "cut.jsonl.gz"
    cut.write_bytes(full[: len(full) // 2])  # truncated download
    lines = list(imp.iter_gz_lines(str(cut)))
    assert 0 < len(lines) < 5000
    assert lines[0] == b'{"n": 0}'


def test_run_import_end_to_end(tmp_path: Path) -> None:
    meta, reviews = write_fixtures(tmp_path)
    out = tmp_path / "ds.sqlite"
    result = imp.run_import("Appliances", out, 100, 50, None, str(meta), str(reviews))
    assert result["meta_bad_lines"] == 1
    assert result["products_kept"] == result["qualified"] == 4  # B1, B2, B6, B7
    assert result["dropped_no_rank"] == 2 and result["dropped_no_price"] == 2
    assert 0 < result["dropped_either_pct"] < 100
    assert not result["reviews_truncated"]

    con = sqlite3.connect(out)
    con.row_factory = sqlite3.Row
    p1 = con.execute("SELECT * FROM products WHERE asin='B000000001'").fetchone()
    assert (p1["bsr"], p1["bsr_sub"], p1["price"], p1["brand"]) == (100, 5, 25.5, "Acme")
    assert p1["category"] == "Ice Makers" and p1["category_path"] == "Appliances > Ice Makers"
    assert (p1["reviews_seen"], p1["reviews_last12"], p1["reviews_prior12"]) == (17, 12, 4)
    assert p1["rating_last12"] is not None and p1["rating_prior12"] == 4.0
    assert '"2023"' in p1["reviews_per_year"]
    assert con.execute("SELECT price FROM products WHERE asin='B000000002'").fetchone()[0] == 1299.0
    p7 = con.execute("SELECT bsr, bsr_category FROM products WHERE asin='B000000007'").fetchone()
    assert tuple(p7) == (30000, "Appliances")
    # Reviews of unknown products, bad ratings, missing timestamps are skipped; HTML stripped.
    assert con.execute("SELECT COUNT(*) FROM reviews WHERE asin='B000000001'").fetchone()[0] == 17
    assert "<br" not in " ".join(r[0] for r in con.execute("SELECT body FROM reviews"))
    assert con.execute("SELECT COUNT(*) FROM reviews WHERE asin='B999999999'").fetchone()[0] == 0
    info = dict(con.execute("SELECT key, value FROM meta").fetchall())
    assert info["category"] == "Appliances" and info["attribution"] == schema.ATTRIBUTION
    assert "licence" in info and info["data_as_of"] == schema.DATASET_AS_OF
    assert info["source_meta_url"] == str(meta) and info["import_date"]
    assert con.execute("SELECT SUM(n_products) FROM category_stats").fetchone()[0] == 4
    con.close()


def test_import_caps_products_reviews_and_lines(tmp_path: Path) -> None:
    out = build_dataset(tmp_path, max_products=2, max_reviews_per_product=3, max_review_lines=5)
    con = sqlite3.connect(out)
    # Best-ranked (lowest BSR) products are kept: rank 50 (B6) and 100 (B1).
    assert {r[0] for r in con.execute("SELECT asin FROM products")} == {"B000000006", "B000000001"}
    assert con.execute("SELECT COUNT(*) FROM reviews").fetchone()[0] <= 3
    info = dict(con.execute("SELECT key, value FROM meta").fetchall())
    assert info["reviews_truncated"] == "1" and info["review_lines_read"] == "5"
    con.close()


def test_import_keeps_newest_reviews(tmp_path: Path) -> None:
    out = build_dataset(tmp_path, max_reviews_per_product=2)
    con = sqlite3.connect(out)
    stamps = sorted(r[0] for r in con.execute("SELECT ts FROM reviews WHERE asin='B000000001'"))
    assert len(stamps) == 2
    # The two newest of the fixtures are 10 and 30 days before the dataset end.
    assert stamps[-1] - stamps[0] == 20 * 86400
    con.close()


def test_import_rejects_bad_category_and_empty_result(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="--category"):
        imp.run_import("../evil", tmp_path / "x.sqlite", 1, 1, None)
    empty = tmp_path / "empty.jsonl"
    empty.write_text(meta_lines()[3] + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No product"):
        imp.run_import("Appliances", tmp_path / "x.sqlite", 1, 1, None, str(empty), str(empty))


def test_cli_main(tmp_path: Path) -> None:
    meta, reviews = write_fixtures(tmp_path)
    out = tmp_path / "cli.sqlite"
    args = ["--category", "Appliances", "--out", str(out)]
    sources = ["--meta-source", str(meta), "--reviews-source", str(reviews)]
    assert imp.main([*args, "--max-products", "10", *sources]) == 0
    assert out.is_file()
    assert imp.main(["--category", "Bad Name", "--out", str(out), *sources]) == 1
    with pytest.raises(SystemExit):
        imp.main([*args, "--max-products", "0"])
    missing = ["--meta-source", str(tmp_path / "missing.gz")]
    assert imp.main([*args, *missing]) == 1
