"""Build a local SQLite file from the Amazon Reviews 2023 dataset (McAuley Lab, UCSD).

Usage (run from ``backend/``)::

    python -m app.data.import_amazon_2023 --category Health_and_Personal_Care \
        --max-products 5000 --max-reviews-per-product 50 --out data/amazon_reviews_2023.sqlite

The gzipped JSONL files are streamed (never fully loaded into memory) from the public
UCSD URLs. Only products with BOTH a parseable Best Sellers Rank and a price are kept.
If ``--max-products`` is smaller than the number of qualifying products, the best-ranked
(lowest BSR) ones are kept. The reviews file can be cut off early with ``--max-review-lines``
(review aggregates are then partial; this is recorded in the ``meta`` table).

LICENCE: the dataset has no explicit licence and is research-oriented; see
``app.data.schema.LICENCE_NOTICE``. Download it yourself; never commit or redistribute it.
"""

import argparse
import ast
import hashlib
import heapq
import json
import logging
import os
import re
import sqlite3
import sys
import zlib
from collections import Counter
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import httpx

from app.data import schema

logger = logging.getLogger("app.data.import_amazon_2023")

CHUNK_BYTES = 256 * 1024
MAX_TITLE_CHARS = 500
MAX_CATEGORY_CHARS = 255
MAX_REVIEW_TITLE_CHARS = 300
MAX_REVIEW_BODY_CHARS = 2000
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
CATEGORY_RE = re.compile(r"^[A-Za-z0-9_]+$")
PROGRESS_EVERY = 100_000
_HTML_TAG_RE = re.compile(r"<[^>]{1,40}>")  # reviews contain "<br />" line breaks


# --------------------------------------------------------------------------- parsing
_RANK_SEGMENT_RE = re.compile(r"#?\s*([\d][\d,\.]*)\s+in\s+(.+?)(?=\s*(?:#\s*\d|$))", re.S)


def _to_rank(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return int(value) if value >= 1 else None
    if isinstance(value, str):
        digits = value.strip().replace(",", "")
        if digits.isdigit() and int(digits) >= 1:
            return int(digits)
    return None


def parse_rank(value: Any) -> list[tuple[str, int]]:
    """Parse a ``Best Sellers Rank`` value into ordered ``(category, rank)`` pairs.

    Accepts a dict (``{"Appliances": 1234}``), a stringified dict (JSON or Python repr), or
    the human format ``"1,234 in Appliances (See Top 100 in Appliances) #5 in Ranges"``.
    The first pair is the top-level category rank. Returns ``[]`` when nothing is parseable.
    """
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("{"):
            for loader in (json.loads, ast.literal_eval):
                try:
                    value = loader(text)
                    break
                except (ValueError, SyntaxError, MemoryError, RecursionError):
                    continue
            else:
                return []
        else:
            pairs: list[tuple[str, int]] = []
            text = re.sub(r"\(See [^)]*\)", " ", text)
            for match in _RANK_SEGMENT_RE.finditer(text):
                rank = _to_rank(match.group(1).split(".")[0])
                name = match.group(2).strip()
                if rank is not None and name:
                    pairs.append((name, rank))
            return pairs
    if isinstance(value, dict):
        out: list[tuple[str, int]] = []
        for name, raw in value.items():
            rank = _to_rank(raw)
            if rank is not None and str(name).strip():
                out.append((str(name).strip(), rank))
        return out
    return []


_PRICE_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?|\.\d+")


def parse_price(value: Any) -> Decimal | None:
    """Parse ``12.99``, ``"$1,299.00"``, ``"from 9.5"`` or ``"$10 - $20"`` (first number)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        text = repr(value)
    elif isinstance(value, str):
        text = value
    else:
        return None
    match = _PRICE_NUM_RE.search(text)
    if match is None or text[: match.start()].rstrip().endswith("-"):  # no number / negative
        return None
    try:
        price = Decimal(match.group(0).replace(",", ""))
    except InvalidOperation:
        return None
    if not price.is_finite() or price <= 0 or price >= Decimal("10000000"):
        return None
    return price.quantize(Decimal("0.01"))


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            loaded = json.loads(value)
        except ValueError:
            return {}
        return loaded if isinstance(loaded, dict) else {}
    return {}


def _clean(value: Any) -> str:
    return " ".join(str(value).split()) if isinstance(value, str | int | float) else ""


def _image_url(images: Any) -> str:
    """First usable image URL from the list-of-dicts (2023) or dict-of-lists layouts."""
    candidates: list[dict[str, Any]] = []
    if isinstance(images, list):
        candidates = [i for i in images if isinstance(i, dict)]
    elif isinstance(images, dict):
        for key in ("large", "hi_res", "thumb"):
            seq = images.get(key)
            if isinstance(seq, list):
                for url in seq:
                    if isinstance(url, str) and url.startswith("http"):
                        return url
        return ""
    for item in candidates:
        for key in ("large", "hi_res", "thumb"):
            url = item.get(key)
            if isinstance(url, str) and url.startswith("http"):
                return url
    return ""


@dataclass(frozen=True)
class ProductRow:
    asin: str
    title: str
    brand: str
    category: str
    category_path: str
    main_category: str
    price: Decimal
    bsr: int
    bsr_category: str
    bsr_sub: int | None
    bsr_sub_category: str
    rating: float
    review_count: int
    image_url: str


def build_product(record: Any, fallback_category: str) -> tuple[ProductRow | None, str]:
    """Convert one metadata record. Returns ``(row, "")`` or ``(None, reason)``.

    Reasons: ``invalid`` (not a usable record), ``no_rank``, ``no_price``, ``no_rank_no_price``.
    """
    if not isinstance(record, dict):
        return None, "invalid"
    asin = record.get("parent_asin")
    title = _clean(record.get("title"))
    if not isinstance(asin, str) or not ASIN_RE.match(asin) or not title:
        return None, "invalid"
    details = _as_dict(record.get("details"))
    ranks = parse_rank(details.get("Best Sellers Rank"))
    price = parse_price(record.get("price"))
    if not ranks and price is None:
        return None, "no_rank_no_price"
    if not ranks:
        return None, "no_rank"
    if price is None:
        return None, "no_price"

    raw_path = record.get("categories")
    path = [_clean(c) for c in raw_path if _clean(c)] if isinstance(raw_path, list) else []
    main = _clean(record.get("main_category"))
    if len(path) > 1:
        category = path[1]
    elif path:
        category = path[0]
    else:
        category = main or fallback_category
    # Ranks are per top-level Amazon category and not comparable across them: prefer the rank in
    # the imported category (e.g. "Appliances"), else the first listed (top-level) one.
    headline = next((r for r in ranks if r[0].lower() == fallback_category.lower()), ranks[0])
    others = [r for r in ranks if r is not headline]
    brand = (
        _clean(details.get("Brand"))
        or _clean(record.get("store"))
        or _clean(details.get("Manufacturer"))
    )
    try:
        rating = float(record.get("average_rating") or 0)
    except (TypeError, ValueError):
        rating = 0.0
    try:
        review_count = max(0, int(record.get("rating_number") or 0))
    except (TypeError, ValueError):
        review_count = 0
    if not 0 <= rating <= 5:
        rating = 0.0
    return (
        ProductRow(
            asin=asin,
            title=title[:MAX_TITLE_CHARS],
            brand=brand[:255],
            category=category[:MAX_CATEGORY_CHARS],
            category_path=" > ".join(path)[:1000],
            main_category=main[:255],
            price=price,
            bsr=headline[1],
            bsr_category=headline[0][:255],
            bsr_sub=others[0][1] if others else None,
            bsr_sub_category=others[0][0][:255] if others else "",
            rating=rating,
            review_count=review_count,
            image_url=_image_url(record.get("images"))[:1000],
        ),
        "",
    )


def parse_timestamp(value: Any) -> int | None:
    """Unix seconds from a seconds or milliseconds timestamp (2023 reviews use ms)."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    ts = int(value)
    if ts > 100_000_000_000:  # milliseconds
        ts //= 1000
    return ts if ts > 0 else None


# --------------------------------------------------------------------------- streaming
@dataclass
class StreamStats:
    lines: int = 0
    bad_lines: int = 0


def _iter_raw_chunks(source: str) -> Iterator[bytes]:
    if re.match(r"^https?://", source):
        with httpx.stream("GET", source, follow_redirects=True, timeout=60.0) as response:
            response.raise_for_status()
            yield from response.iter_raw(CHUNK_BYTES)
    else:
        with open(source, "rb") as fh:
            while chunk := fh.read(CHUNK_BYTES):
                yield chunk


def iter_gz_lines(source: str, max_lines: int | None = None) -> Iterator[bytes]:
    """Stream decompressed lines of a gzip file from a URL or local path.

    Tolerates a truncated stream (a cut-off download yields the lines decoded so far).
    Plain (non-gzip) files are also accepted, which keeps test fixtures simple.
    """
    decomp = zlib.decompressobj(wbits=31)
    buffer = b""
    emitted = 0
    plain: bool | None = None
    try:
        for raw in _iter_raw_chunks(source):
            if plain is None:
                plain = not raw.startswith(b"\x1f\x8b")
            data = raw if plain else decomp.decompress(raw)
            buffer += data
            *lines, buffer = buffer.split(b"\n")
            for line in lines:
                if line.strip():
                    yield line.strip()
                    emitted += 1
                    if max_lines is not None and emitted >= max_lines:
                        return
            if not plain and decomp.eof:
                break
    except (zlib.error, EOFError, httpx.TransportError) as exc:
        logger.warning("Stream ended early (%s); using the lines read so far", exc)
    if buffer.strip() and (max_lines is None or emitted < max_lines):
        yield buffer.strip()


def iter_json(source: str, stats: StreamStats, max_lines: int | None = None) -> Iterator[Any]:
    """Yield parsed JSON objects, counting and skipping malformed lines."""
    for line in iter_gz_lines(source, max_lines):
        stats.lines += 1
        try:
            yield json.loads(line)
        except (ValueError, UnicodeDecodeError):
            stats.bad_lines += 1
        if stats.lines % PROGRESS_EVERY == 0:
            logger.info("  ... %d lines read (%d bad)", stats.lines, stats.bad_lines)


# --------------------------------------------------------------------------- pass 1: metadata
@dataclass
class MetaResult:
    products: dict[str, ProductRow]
    category_counts: Counter[str]
    stats: StreamStats
    drops: Counter[str] = field(default_factory=Counter)
    qualified: int = 0


def read_metadata(source: str, category: str, max_products: int) -> MetaResult:
    stats = StreamStats()
    drops: Counter[str] = Counter()
    counts: Counter[str] = Counter()
    kept: dict[str, ProductRow] = {}
    heap: list[tuple[int, str]] = []  # (-bsr, asin): root is the worst-ranked kept product
    seen: set[str] = set()
    qualified = 0
    fallback = category.replace("_", " ")
    for record in iter_json(source, stats):
        row, reason = build_product(record, fallback)
        if row is None:
            drops[reason] += 1
            continue
        if row.asin in seen:
            drops["duplicate"] += 1
            continue
        seen.add(row.asin)
        qualified += 1
        counts[row.category] += 1
        if len(heap) < max_products:
            heapq.heappush(heap, (-row.bsr, row.asin))
            kept[row.asin] = row
        elif heap and row.bsr < -heap[0][0]:
            _, evicted = heapq.heappushpop(heap, (-row.bsr, row.asin))
            kept.pop(evicted, None)
            kept[row.asin] = row
    return MetaResult(kept, counts, stats, drops, qualified)


# --------------------------------------------------------------------------- pass 2: reviews
@dataclass
class _Agg:
    seen: int = 0
    per_year: Counter[int] = field(default_factory=Counter)
    last_n: int = 0
    last_sum: float = 0.0
    prior_n: int = 0
    prior_sum: float = 0.0
    heap: list[tuple[int, int, tuple[Any, ...]]] = field(default_factory=list)


@dataclass
class ReviewResult:
    aggs: dict[str, _Agg]
    stats: StreamStats
    matched: int
    max_ts: int | None
    truncated: bool


def review_id(asin: str, user_id: str, ts: int, body: str) -> str:
    digest = hashlib.sha1(f"{user_id}|{ts}|{body[:200]}".encode(), usedforsecurity=False)
    return f"{asin}-{digest.hexdigest()[:12]}"


def read_reviews(
    source: str,
    asins: set[str],
    per_product: int,
    as_of: date,
    max_lines: int | None,
) -> ReviewResult:
    stats = StreamStats()
    aggs: dict[str, _Agg] = {a: _Agg() for a in asins}
    end = datetime.combine(as_of, datetime.max.time(), tzinfo=UTC).timestamp()
    year_start = end - 365 * 86400
    prior_start = end - 730 * 86400
    matched = 0
    max_ts: int | None = None
    counter = 0
    for record in iter_json(source, stats, max_lines):
        if not isinstance(record, dict):
            stats.bad_lines += 1
            continue
        asin = record.get("parent_asin")
        agg = aggs.get(asin) if isinstance(asin, str) else None
        ts = parse_timestamp(record.get("timestamp"))
        rating_raw = record.get("rating")
        if agg is None or ts is None or not isinstance(rating_raw, int | float):
            continue
        rating = int(round(rating_raw))
        if not 1 <= rating <= 5:
            continue
        matched += 1
        max_ts = ts if max_ts is None else max(max_ts, ts)
        agg.seen += 1
        agg.per_year[datetime.fromtimestamp(ts, UTC).year] += 1
        if year_start < ts <= end:
            agg.last_n += 1
            agg.last_sum += rating
        elif prior_start < ts <= year_start:
            agg.prior_n += 1
            agg.prior_sum += rating
        title = _clean(_HTML_TAG_RE.sub(" ", str(record.get("title") or "")))[
            :MAX_REVIEW_TITLE_CHARS
        ]
        body = " ".join(_HTML_TAG_RE.sub(" ", str(record.get("text") or "")).split())[
            :MAX_REVIEW_BODY_CHARS
        ]
        rid = review_id(str(asin), str(record.get("user_id") or ""), ts, body)
        counter += 1
        item = (
            ts,
            counter,
            (rid, str(asin), rating, title, body, ts, int(bool(record.get("verified_purchase")))),
        )
        if len(agg.heap) < per_product:
            heapq.heappush(agg.heap, item)
        elif per_product and ts > agg.heap[0][0]:
            heapq.heapreplace(agg.heap, item)
    truncated = max_lines is not None and stats.lines >= max_lines
    return ReviewResult(aggs, stats, matched, max_ts, truncated)


# --------------------------------------------------------------------------- output
def write_sqlite(
    out: Path,
    meta: MetaResult,
    reviews: ReviewResult,
    info: dict[str, str],
) -> tuple[int, int]:
    """Write the SQLite file atomically (temp file + replace). Returns (products, reviews)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(schema.SCHEMA_SQL)
        product_rows = []
        for asin, p in meta.products.items():
            a = reviews.aggs[asin]
            product_rows.append(
                (
                    asin, p.title, p.brand, p.category, p.category_path, p.main_category,
                    float(p.price), p.bsr, p.bsr_category, p.bsr_sub, p.bsr_sub_category,
                    p.rating, p.review_count, p.image_url,
                    a.seen, a.last_n, a.prior_n,
                    a.last_sum / a.last_n if a.last_n else None,
                    a.prior_sum / a.prior_n if a.prior_n else None,
                    json.dumps({str(y): n for y, n in sorted(a.per_year.items())}),
                )
            )  # fmt: skip
        conn.executemany(
            "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", product_rows
        )
        review_rows = [item[2] for a in reviews.aggs.values() for item in a.heap]
        conn.executemany("INSERT OR IGNORE INTO reviews VALUES (?,?,?,?,?,?,?)", review_rows)
        conn.executemany(
            "INSERT INTO category_stats VALUES (?,?)", sorted(meta.category_counts.items())
        )
        conn.executemany("INSERT INTO meta VALUES (?,?)", sorted(info.items()))
        conn.commit()
        conn.execute("VACUUM")
    finally:
        conn.close()
    os.replace(tmp, out)
    return len(product_rows), len(review_rows)


def pct(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def run_import(
    category: str,
    out: Path,
    max_products: int,
    max_reviews_per_product: int,
    max_review_lines: int | None,
    meta_source: str | None = None,
    reviews_source: str | None = None,
) -> dict[str, Any]:
    """Run the full import and return a stats dict (also logged)."""
    if not CATEGORY_RE.match(category):
        raise ValueError("--category must look like 'Health_and_Personal_Care'")
    meta_src = meta_source or schema.META_URL.format(category=category)
    reviews_src = reviews_source or schema.REVIEWS_URL.format(category=category)
    as_of = date.fromisoformat(schema.DATASET_AS_OF)

    logger.info("Reading metadata from %s", meta_src)
    meta = read_metadata(meta_src, category, max_products)
    logger.info(
        "Metadata: %d lines, %d bad; %d qualify (rank+price); keeping %d",
        meta.stats.lines, meta.stats.bad_lines, meta.qualified, len(meta.products),
    )  # fmt: skip
    if not meta.products:
        raise ValueError("No product has both a parseable Best Sellers Rank and a price")

    logger.info("Reading reviews from %s (max lines: %s)", reviews_src, max_review_lines)
    reviews = read_reviews(
        reviews_src, set(meta.products), max_reviews_per_product, as_of, max_review_lines
    )
    logger.info(
        "Reviews: %d lines read, %d bad, %d matched kept products%s",
        reviews.stats.lines, reviews.stats.bad_lines, reviews.matched,
        " (TRUNCATED by --max-review-lines: aggregates are partial)" if reviews.truncated else "",
    )  # fmt: skip

    total = meta.stats.lines - meta.stats.bad_lines
    dropped_rank = meta.drops["no_rank"] + meta.drops["no_rank_no_price"]
    dropped_price = meta.drops["no_price"] + meta.drops["no_rank_no_price"]
    info = {
        "schema_version": schema.SCHEMA_VERSION,
        "dataset_name": schema.DATASET_NAME,
        "dataset_version": schema.DATASET_VERSION,
        "data_as_of": schema.DATASET_AS_OF,
        "category": category,
        "source_meta_url": meta_src,
        "source_reviews_url": reviews_src,
        "import_date": datetime.now(UTC).date().isoformat(),
        "attribution": schema.ATTRIBUTION,
        "licence": schema.LICENCE_NOTICE,
        "meta_lines": str(meta.stats.lines),
        "meta_bad_lines": str(meta.stats.bad_lines),
        "meta_valid_records": str(total),
        "dropped_no_rank": str(dropped_rank),
        "dropped_no_price": str(dropped_price),
        "qualified_products": str(meta.qualified),
        "max_products": str(max_products),
        "review_lines_read": str(reviews.stats.lines),
        "reviews_truncated": "1" if reviews.truncated else "0",
        "max_reviews_per_product": str(max_reviews_per_product),
        "observed_max_review_date": (
            datetime.fromtimestamp(reviews.max_ts, UTC).date().isoformat() if reviews.max_ts else ""
        ),
    }
    n_products, n_reviews = write_sqlite(out, meta, reviews, info)
    result: dict[str, Any] = {
        "meta_lines": meta.stats.lines,
        "meta_bad_lines": meta.stats.bad_lines,
        "valid_records": total,
        "dropped_no_rank": dropped_rank,
        "dropped_no_price": dropped_price,
        "dropped_no_rank_pct": pct(dropped_rank, total),
        "dropped_no_price_pct": pct(dropped_price, total),
        "dropped_either": total - meta.qualified,
        "dropped_either_pct": pct(total - meta.qualified, total),
        "qualified": meta.qualified,
        "products_kept": n_products,
        "reviews_stored": n_reviews,
        "review_lines_read": reviews.stats.lines,
        "reviews_truncated": reviews.truncated,
        "db_bytes": out.stat().st_size,
        "out": str(out),
    }
    logger.info("Import complete: %s", json.dumps(result))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.data.import_amazon_2023",
        description="Import a category of Amazon Reviews 2023 into a local SQLite file.",
    )
    parser.add_argument("--category", required=True, help="e.g. Health_and_Personal_Care")
    parser.add_argument("--max-products", type=int, default=5000)
    parser.add_argument("--max-reviews-per-product", type=int, default=50)
    parser.add_argument(
        "--max-review-lines",
        type=int,
        default=5_000_000,
        help="stop reading the reviews file after this many lines (caps the download)",
    )
    parser.add_argument(
        "--out",
        help=f"output file (default: <repo>/{schema.DEFAULT_DATASET_PATH})",
    )
    parser.add_argument("--meta-source", help="override metadata URL or local .jsonl(.gz) path")
    parser.add_argument("--reviews-source", help="override reviews URL or local path")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.warning("Dataset licence: %s", schema.LICENCE_NOTICE)
    if args.max_products < 1 or args.max_reviews_per_product < 0 or args.max_review_lines < 1:
        parser.error("limits must be positive")
    try:
        run_import(
            args.category,
            Path(args.out)
            if args.out
            else schema.resolve_dataset_path(schema.DEFAULT_DATASET_PATH),
            args.max_products,
            args.max_reviews_per_product,
            args.max_review_lines,
            args.meta_source,
            args.reviews_source,
        )
    except (ValueError, httpx.HTTPError, OSError) as exc:
        logger.error("Import failed: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
