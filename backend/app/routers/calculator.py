"""Stateless profit calculator endpoints."""

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.calculator import (
    CalculateRequest,
    CalculationResult,
    SimulateRequest,
    SimulateResponse,
)
from app.services import calculator_service

router = APIRouter(
    prefix="/calculator", tags=["calculator"], dependencies=[Depends(get_current_user)]
)


@router.post("/calculate", response_model=CalculationResult)
async def calculate(payload: CalculateRequest) -> CalculationResult:
    return calculator_service.calculate(payload)


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(payload: SimulateRequest) -> SimulateResponse:
    return calculator_service.simulate(payload)
