"""File upload endpoints (user avatars)."""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, UploadFile, status

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.imports import AvatarUpdated
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post(
    "/avatar",
    response_model=AvatarUpdated,
    dependencies=[Depends(upload_service.content_length_guard(upload_service.AVATAR_MAX_BYTES))],
)
async def upload_avatar(
    file: Annotated[UploadFile, File()], user: User = Depends(get_current_user)
) -> AvatarUpdated:
    await upload_service.save_avatar(user.id, file)
    return AvatarUpdated(updated=True)


@router.get("/avatar")
def get_avatar(user: User = Depends(get_current_user)) -> Response:
    data, content_type = upload_service.load_avatar(user.id)
    return Response(
        content=data,
        media_type=content_type,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-cache"},
    )


@router.delete("/avatar", status_code=status.HTTP_204_NO_CONTENT)
def delete_avatar(user: User = Depends(get_current_user)) -> Response:
    upload_service.delete_avatar(user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
