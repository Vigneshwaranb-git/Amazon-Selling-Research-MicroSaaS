"""Schemas for file uploads and CSV imports."""

from pydantic import BaseModel


class AvatarUpdated(BaseModel):
    updated: bool


class RowError(BaseModel):
    """`row` is the 1-based data row number (the header line is not counted)."""

    row: int
    message: str


class AsinImportResult(BaseModel):
    added: int
    skipped: int
    errors: list[RowError]


class CostSheetImportResult(BaseModel):
    created: int
    errors: list[RowError]
