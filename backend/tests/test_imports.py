"""Tests for CSV imports (ASIN lists and cost sheets) and CSV export safety."""

from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_current_user
from app.main import app
from app.models.cost_model import CostModel
from app.models.product import Product
from app.models.user import User
from app.services import product_service
from app.services.product_service import _csv_safe
from app.services.providers import get_product_data_provider
from app.services.providers.mock import MockProductDataProvider

ASINS = "/api/v1/imports/asins"
COSTS = "/api/v1/imports/cost-sheet"
LISTS = "/api/v1/tracking-lists"
COST_HEADER = (
    "name,asin,unit_cost,shipping_cost,referral_fee,fba_fulfillment_fee,"
    "storage_fee,vat_tax,selling_price\n"
)


@pytest.fixture
def users(client: TestClient, db_session: Session) -> Iterator[dict[int, User]]:
    out: dict[int, User] = {}
    for uid in (1, 2):
        u = User(id=uid, email=f"u{uid}@example.com")
        db_session.add(u)
        out[uid] = u
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: out[1]
    yield out
    app.dependency_overrides.pop(get_current_user, None)


def _csv(client: TestClient, url: str, body: bytes | str, **params: object) -> httpx.Response:
    data = body.encode() if isinstance(body, str) else body
    return client.post(url, params=params, files={"file": ("x.csv", data, "text/csv")})  # type: ignore[arg-type]


def _new_list(client: TestClient, name: str = "L") -> int:
    return int(client.post(LISTS, json={"name": name}).json()["id"])


def test_requires_auth(client: TestClient) -> None:
    assert _csv(client, ASINS, "asin\n", new_list_name="x").status_code == 401
    assert _csv(client, COSTS, "name\n").status_code == 401


def test_asins_import_dedupe_and_errors(client: TestClient, users: dict[int, User]) -> None:
    lid = _new_list(client)
    body = "asin,note\nb012345678,a\nB012345678,dup\nB0AAAAAAAA,x\nbad!,y\n\n,z\nB0BBBBBBBB\n"
    r = _csv(client, ASINS, body, tracking_list_id=lid)
    assert r.status_code == 200
    out = r.json()
    assert out["added"] == 3
    assert out["skipped"] == 1
    assert [e["row"] for e in out["errors"]] == [4, 6]
    again = _csv(client, ASINS, "asin\nB012345678\nB0AAAAAAAA\n", tracking_list_id=lid).json()
    assert again == {"added": 0, "skipped": 2, "errors": []}
    detail = client.get(f"{LISTS}/{lid}").json()
    got = sorted(p["asin"] for p in detail["products"])
    assert got == ["B012345678", "B0AAAAAAAA", "B0BBBBBBBB"]


def test_asins_import_new_list_and_bom(client: TestClient, users: dict[int, User]) -> None:
    r = _csv(client, ASINS, b"\xef\xbb\xbfASIN\r\nB012345678\r\n", new_list_name="  Fresh ")
    assert r.status_code == 200
    assert r.json()["added"] == 1
    lists = client.get(LISTS).json()
    assert [(x["name"], x["product_count"]) for x in lists] == [("Fresh", 1)]
    assert _csv(client, ASINS, "asin\nB012345678\n", new_list_name="fresh").status_code == 409


def test_asins_target_params(client: TestClient, users: dict[int, User]) -> None:
    lid = _new_list(client)
    assert _csv(client, ASINS, "asin\n").status_code == 422
    both = _csv(client, ASINS, "asin\n", tracking_list_id=lid, new_list_name="n")
    assert both.status_code == 422
    assert _csv(client, ASINS, "asin\n", new_list_name="   ").status_code == 422


def test_asins_list_ownership(client: TestClient, users: dict[int, User]) -> None:
    lid = _new_list(client)
    app.dependency_overrides[get_current_user] = lambda: users[2]
    r = _csv(client, ASINS, "asin\nB012345678\n", tracking_list_id=lid)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"
    assert _csv(client, ASINS, "asin\n", tracking_list_id=99999).status_code == 404


def test_asins_unknown_product_reported(client: TestClient, users: dict[int, User]) -> None:
    class _NoneProvider(MockProductDataProvider):
        async def get_product(self, asin: str) -> None:  # type: ignore[override]
            return None

    app.dependency_overrides[get_product_data_provider] = lambda: _NoneProvider()
    try:
        r = _csv(client, ASINS, "asin\nB0ZZZZZZZZ\n", new_list_name="n")
    finally:
        app.dependency_overrides.pop(get_product_data_provider, None)
    assert r.json()["added"] == 0
    assert r.json()["errors"] == [{"row": 1, "message": "Product not found for this ASIN"}]


@pytest.mark.parametrize(
    ("body", "status"),
    [
        (b"", 400),
        (b"asin\nB012345678\x00\n", 400),
        (b"\x89PNG\r\n\x1a\n\x00\x00", 400),
        (b"asin\n\xff\xfe\xfa\n", 400),
        (b"name\nfoo\n", 422),
        (b"\n\n", 400),
    ],
)
def test_asins_bad_files(
    client: TestClient, users: dict[int, User], body: bytes, status: int
) -> None:
    r = _csv(client, ASINS, body, new_list_name="n")
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == "INVALID_FILE"


def test_asins_limits(client: TestClient, users: dict[int, User]) -> None:
    rows = "asin\n" + "\n".join(f"B{i:09d}" for i in range(1001)) + "\n"
    r = _csv(client, ASINS, rows, new_list_name="big")
    assert r.status_code == 422
    assert client.get(LISTS).json() == []  # nothing was created
    big = _csv(client, ASINS, "asin\n" + "A" * (1024 * 1024), new_list_name="big")
    assert big.status_code == 413
    assert big.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_asins_long_field_and_extra_columns(client: TestClient, users: dict[int, User]) -> None:
    body = "asin\n" + "B" * 600 + "\nB012345678,extra\n"
    r = _csv(client, ASINS, body, new_list_name="n")
    assert r.json()["added"] == 0
    assert [e["row"] for e in r.json()["errors"]] == [1, 2]


def test_cost_sheet_import(client: TestClient, users: dict[int, User], db_session: Session) -> None:
    body = COST_HEADER + (
        "Widget,b012345678,10.00,2,3,4,0.5,0.5,30\n"  # row 1 ok
        "Neg,,-1,0,0,0,0,0,30\n"  # row 2 negative
        "Garbage,,abc,0,0,0,0,0,30\n"  # row 3
        "NaN,,NaN,0,0,0,0,0,30\n"  # row 4
        ",,1,0,0,0,0,0,30\n"  # row 5 no name
        "BadAsin,xyz,1,0,0,0,0,0,30\n"  # row 6
        "NoPrice,,1,0,0,0,0,0,\n"  # row 7
        "Prec,,1.234,0,0,0,0,0,30\n"  # row 8 too many decimals
        "Min,,5,,,,,,20\n"  # row 9 missing fees default to 0
    )
    r = _csv(client, COSTS, body)
    assert r.status_code == 200
    out = r.json()
    assert out["created"] == 2
    assert [e["row"] for e in out["errors"]] == [2, 3, 4, 5, 6, 7, 8]
    models = db_session.execute(select(CostModel).order_by(CostModel.id)).scalars().all()
    assert [m.user_id for m in models] == [1, 1]
    w = models[0]
    assert (w.name, w.asin) == ("Widget", "B012345678")
    assert float(w.net_profit) == pytest.approx(10.0)  # type: ignore[arg-type]
    assert float(w.roi) == pytest.approx(83.33, abs=0.01)  # type: ignore[arg-type]
    assert float(w.margin) == pytest.approx(33.33, abs=0.01)  # type: ignore[arg-type]
    assert float(models[1].net_profit) == pytest.approx(15.0)  # type: ignore[arg-type]


def test_cost_sheet_formula_cells_stored_as_text(
    client: TestClient, users: dict[int, User], db_session: Session
) -> None:
    body = COST_HEADER + '=HYPERLINK("evil"),,1,0,0,0,0,0,5\n'
    assert _csv(client, COSTS, body).json()["created"] == 1
    assert db_session.execute(select(CostModel.name)).scalar_one() == '=HYPERLINK("evil")'


def test_cost_sheet_bom_and_minimal_header(client: TestClient, users: dict[int, User]) -> None:
    r = _csv(client, COSTS, b"\xef\xbb\xbfName,Unit_Cost,Selling_Price\r\nA,1,5\r\n")
    assert r.json() == {"created": 1, "errors": []}


def test_cost_sheet_bad_files(client: TestClient, users: dict[int, User]) -> None:
    assert _csv(client, COSTS, "name,unit_cost\nA,1\n").status_code == 422
    assert _csv(client, COSTS, b"name,unit_cost,selling_price\nA\x00,1,2\n").status_code == 400
    rows = "name,unit_cost,selling_price\n" + "A,1,2\n" * 1001
    assert _csv(client, COSTS, rows).status_code == 422
    extra = _csv(client, COSTS, "name,unit_cost,selling_price\nA,1,2,3,4\n")
    assert extra.json()["created"] == 0


def test_cost_sheet_scoped_to_user(
    client: TestClient, users: dict[int, User], db_session: Session
) -> None:
    app.dependency_overrides[get_current_user] = lambda: users[2]
    _csv(client, COSTS, "name,unit_cost,selling_price\nA,1,2\n")
    assert db_session.execute(select(CostModel.user_id)).scalar_one() == 2


def test_csv_safe_numbers_and_strings() -> None:
    assert _csv_safe(-12.5) == "-12.5"
    assert _csv_safe(-3) == "-3"
    assert _csv_safe(None) == ""
    assert _csv_safe(4.0) == "4.0"
    assert _csv_safe("=1+1") == "'=1+1"
    assert _csv_safe("-5") == "'-5"
    assert _csv_safe("+x") == "'+x"
    assert _csv_safe("@sum") == "'@sum"
    assert _csv_safe("\tx") == "'\tx"
    assert _csv_safe("\rx") == "'\rx"
    assert _csv_safe("normal") == "normal"


def test_export_negative_numbers_not_prefixed() -> None:
    p = Product(asin="B0NEGATIVE0", title="=evil", price=1)
    p.estimated_monthly_sales = -5
    out = product_service.products_to_csv([p])
    assert "'=evil" in out
    assert ",-5," in out
    assert "'-5" not in out
