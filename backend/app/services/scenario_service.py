"""CRUD for saved profit scenarios, always scoped to the owning user."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.exceptions import NotFoundError
from app.models.cost_model import CostModel
from app.schemas.scenario import ScenarioBase
from app.services import calculator_service as calc


def _apply(model: CostModel, data: ScenarioBase) -> None:
    for field, value in data.model_dump().items():
        setattr(model, field, value)
    result = calc.calculate(data)
    model.net_profit = result.net_profit
    model.roi = result.roi_pct
    model.margin = result.margin_pct


def list_scenarios(db: Session, user_id: int, skip: int = 0, limit: int = 100) -> list[CostModel]:
    stmt = (
        select(CostModel)
        .where(CostModel.user_id == user_id)
        .order_by(CostModel.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


def get_scenario(db: Session, user_id: int, scenario_id: int) -> CostModel:
    model = db.scalar(
        select(CostModel).where(CostModel.id == scenario_id, CostModel.user_id == user_id)
    )
    if model is None:
        raise NotFoundError("Scenario")
    return model


def create_scenario(db: Session, user_id: int, data: ScenarioBase) -> CostModel:
    model = CostModel(user_id=user_id)
    _apply(model, data)
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def update_scenario(db: Session, user_id: int, scenario_id: int, data: ScenarioBase) -> CostModel:
    model = get_scenario(db, user_id, scenario_id)
    _apply(model, data)
    db.commit()
    db.refresh(model)
    return model


def delete_scenario(db: Session, user_id: int, scenario_id: int) -> None:
    model = get_scenario(db, user_id, scenario_id)
    db.delete(model)
    db.commit()
