"""CSV import endpoints (multipart field `file`, max 1 MB / 1000 rows)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.imports import AsinImportResult, CostSheetImportResult
from app.services import import_service, upload_service
from app.services.providers import get_product_data_provider
from app.services.providers.base import ProductDataProvider

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
    dependencies=[Depends(upload_service.content_length_guard(import_service.IMPORT_MAX_BYTES))],
)


@router.post("/asins", response_model=AsinImportResult)
async def import_asins(
    file: Annotated[UploadFile, File()],
    tracking_list_id: int | None = Query(None, ge=1),
    new_list_name: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
    provider: ProductDataProvider = Depends(get_product_data_provider),
    user: User = Depends(get_current_user),
) -> AsinImportResult:
    return await import_service.import_asins(
        db, provider, user.id, file, tracking_list_id, new_list_name
    )


@router.post("/cost-sheet", response_model=CostSheetImportResult)
async def import_cost_sheet(
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> CostSheetImportResult:
    return await import_service.import_cost_sheet(db, user.id, file)
