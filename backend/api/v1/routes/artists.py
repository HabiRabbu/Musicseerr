import logging
from fastapi import APIRouter, Depends
from api.v1.schemas.artist import ArtistInfo
from core.dependencies import get_artist_service
from services.artist_service import ArtistService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/artist", tags=["artist"])


@router.get("/{artist_id}", response_model=ArtistInfo)
async def get_artist(
    artist_id: str,
    artist_service: ArtistService = Depends(get_artist_service)
):
    return await artist_service.get_artist_info(artist_id)
