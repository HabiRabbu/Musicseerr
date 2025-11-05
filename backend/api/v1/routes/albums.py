import logging
from fastapi import APIRouter, Depends
from api.v1.schemas.album import AlbumInfo
from core.dependencies import get_album_service
from services.album_service import AlbumService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/album", tags=["album"])


@router.get("/{album_id}", response_model=AlbumInfo)
async def get_album(
    album_id: str,
    album_service: AlbumService = Depends(get_album_service)
):
    return await album_service.get_album_info(album_id)
