"""CSV imports: ASIN lists into tracking lists and cost sheets into scenarios.

Row numbering: the header line is not counted; the first line after it is data
row 1. Blank lines consume a row number but are otherwise ignored.
"""

import csv
import io
import logging
import re
from decimal import Decimal, InvalidOperation

from fastapi import UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import AppException, NotFoundError
from app.models.product import Product
from app.models.tracking_list import TrackedProduct, TrackingList
from app.schemas.imports import AsinImportResult, CostSheetImportResult, RowError
from app.schemas.scenario import ScenarioBase
from app.schemas.tracking_list import TrackingListCreate
from app.services import product_service, scenario_service, tracking_service
from app.services.providers.base import ProductDataProvider
from app.services.upload_service import InvalidFileError, read_limited

logger = logging.getLogger(__name__)

IMPORT_MAX_BYTES = 1024 * 1024
IMPORT_MAX_ROWS = 1000
MAX_FIELD_LEN = 500
MAX_COLUMNS = 30

ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
MONEY_COLUMNS = (
    "unit_cost",
    "shipping_cost",
    "referral_fee",
    "fba_fulfillment_fee",
    "storage_fee",
    "vat_tax",
    "selling_price",
)
REQUIRED_MONEY = ("unit_cost", "selling_price")


async def _load_rows(
    file: UploadFile, required: tuple[str, ...]
) -> tuple[list[str], list[list[str]]]:
    """Return (header, data_rows) after validating size, encoding and shape."""
    data = await read_limited(file, IMPORT_MAX_BYTES)
    if not data.strip():
        raise InvalidFileError("Uploaded file is empty")
    if b"\x00" in data:
        raise InvalidFileError("File is not a text CSV (binary content detected)")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise InvalidFileError("File must be UTF-8 encoded text") from None

    reader = csv.reader(io.StringIO(text, newline=""))
    rows: list[list[str]] = []
    header: list[str] | None = None
    try:
        for raw in reader:
            if header is None:
                if not any(c.strip() for c in raw):
                    continue
                header = [c.strip().lower() for c in raw]
                if len(header) > MAX_COLUMNS or any(len(c) > 100 for c in header):
                    raise InvalidFileError("CSV header is invalid", 422)
                continue
            if len(rows) >= IMPORT_MAX_ROWS:
                raise InvalidFileError(f"Too many rows (max {IMPORT_MAX_ROWS})", 422)
            rows.append(raw)
    except csv.Error:
        raise InvalidFileError("Malformed CSV content") from None
    if header is None:
        raise InvalidFileError("CSV has no header row", 422)
    missing = [c for c in required if c not in header]
    if missing:
        raise InvalidFileError(
            f"CSV header is missing required column(s): {', '.join(missing)}", 422
        )
    return header, rows


def _cell(header: list[str], row: list[str], column: str) -> str | None:
    """Stripped cell value, or None when the column is absent from the header or row."""
    try:
        idx = header.index(column)
    except ValueError:
        return None
    if idx >= len(row):
        return None
    return row[idx].strip()


def _check_row_shape(header: list[str], row: list[str]) -> str | None:
    if len(row) > len(header):
        return "Row has more columns than the header"
    if any(len(c) > MAX_FIELD_LEN for c in row):
        return f"A field exceeds {MAX_FIELD_LEN} characters"
    return None


def _check_target(tracking_list_id: int | None, new_list_name: str | None) -> None:
    if (tracking_list_id is None) == (new_list_name is None):
        raise InvalidFileError("Provide exactly one of tracking_list_id or new_list_name", 422)


# ---------------------------------------------------------------------------
# ASIN import
# ---------------------------------------------------------------------------


def _resolve_list(
    db: Session, user_id: int, tracking_list_id: int | None, new_list_name: str | None
) -> TrackingList:
    if tracking_list_id is not None:
        return tracking_service.get_owned_list(db, user_id, tracking_list_id)
    try:
        name = TrackingListCreate(name=new_list_name or "").name
    except ValidationError:
        raise InvalidFileError("new_list_name must be 1-100 non-blank characters", 422) from None
    return tracking_service.create_list(db, user_id, name)


async def import_asins(
    db: Session,
    provider: ProductDataProvider,
    user_id: int,
    file: UploadFile,
    tracking_list_id: int | None,
    new_list_name: str | None,
) -> AsinImportResult:
    _check_target(tracking_list_id, new_list_name)
    if tracking_list_id is not None:
        # 404 before touching the file body when the list is not ours.
        tracking_service.get_owned_list(db, user_id, tracking_list_id)

    header, rows = await _load_rows(file, ("asin",))
    tl = _resolve_list(db, user_id, tracking_list_id, new_list_name)

    existing = set(
        db.execute(
            select(Product.asin)
            .join(TrackedProduct, TrackedProduct.product_id == Product.id)
            .where(TrackedProduct.tracking_list_id == tl.id)
        ).scalars()
    )
    seen: set[str] = set()
    added = skipped = 0
    errors: list[RowError] = []

    for n, row in enumerate(rows, start=1):
        if not any(c.strip() for c in row):
            continue
        shape_err = _check_row_shape(header, row)
        if shape_err:
            errors.append(RowError(row=n, message=shape_err))
            continue
        asin = (_cell(header, row, "asin") or "").upper()
        if not ASIN_RE.fullmatch(asin):
            errors.append(RowError(row=n, message="ASIN must be 10 letters/digits"))
            continue
        if asin in seen or asin in existing:
            skipped += 1
            continue
        seen.add(asin)
        try:
            product = await product_service.get_or_fetch_product(db, provider, asin)
        except NotFoundError:
            errors.append(RowError(row=n, message="Product not found for this ASIN"))
            continue
        except AppException:
            raise
        except Exception:
            db.rollback()
            logger.exception("Product lookup failed during import for %s", asin)
            errors.append(RowError(row=n, message="Product lookup failed"))
            continue
        db.add(TrackedProduct(tracking_list_id=tl.id, product_id=product.id))
        db.commit()
        added += 1

    return AsinImportResult(added=added, skipped=skipped, errors=errors)


# ---------------------------------------------------------------------------
# Cost sheet import
# ---------------------------------------------------------------------------


def _parse_money(raw: str | None, column: str, required: bool) -> Decimal:
    if raw is None or raw == "":
        if required:
            raise ValueError(f"{column} is required")
        return Decimal("0")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"{column} is not a valid number") from None
    if not value.is_finite():
        raise ValueError(f"{column} is not a valid number")
    if value < 0:
        raise ValueError(f"{column} must not be negative")
    return value


def _row_to_scenario(header: list[str], row: list[str]) -> ScenarioBase:
    shape_err = _check_row_shape(header, row)
    if shape_err:
        raise ValueError(shape_err)
    name = _cell(header, row, "name") or ""
    if not name:
        raise ValueError("name is required")
    asin_raw = (_cell(header, row, "asin") or "").upper()
    if asin_raw and not ASIN_RE.fullmatch(asin_raw):
        raise ValueError("asin must be 10 letters/digits")
    money = {
        col: _parse_money(_cell(header, row, col), col, required=col in REQUIRED_MONEY)
        for col in MONEY_COLUMNS
    }
    try:
        return ScenarioBase(name=name, asin=asin_raw or None, **money)
    except ValidationError as exc:
        err = exc.errors()[0]
        field = ".".join(str(p) for p in err["loc"]) or "row"
        raise ValueError(f"{field}: {err['msg']}") from None


async def import_cost_sheet(db: Session, user_id: int, file: UploadFile) -> CostSheetImportResult:
    header, rows = await _load_rows(file, ("name", *REQUIRED_MONEY))
    created = 0
    errors: list[RowError] = []
    for n, row in enumerate(rows, start=1):
        if not any(c.strip() for c in row):
            continue
        try:
            data = _row_to_scenario(header, row)
        except ValueError as exc:
            errors.append(RowError(row=n, message=str(exc)))
            continue
        scenario_service.create_scenario(db, user_id, data)
        created += 1
    return CostSheetImportResult(created=created, errors=errors)
