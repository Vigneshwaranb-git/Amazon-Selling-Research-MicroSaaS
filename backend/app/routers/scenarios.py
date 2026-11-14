"""Saved scenario CRUD, scoped to the current user."""

from typing import Any, cast

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.cost_model import CostModel
from app.schemas.scenario import ScenarioCreate, ScenarioResponse, ScenarioUpdate
from app.services import scenario_service

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _uid(user: object) -> int:
    return int(cast(Any, user).id)


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CostModel]:
    return scenario_service.list_scenarios(db, _uid(user), skip, limit)


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: ScenarioCreate,
    user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CostModel:
    return scenario_service.create_scenario(db, _uid(user), payload)


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CostModel:
    return scenario_service.get_scenario(db, _uid(user), scenario_id)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: int,
    payload: ScenarioUpdate,
    user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CostModel:
    return scenario_service.update_scenario(db, _uid(user), scenario_id, payload)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: int,
    user: object = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    scenario_service.delete_scenario(db, _uid(user), scenario_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
