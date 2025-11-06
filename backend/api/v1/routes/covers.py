import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Path, Query, Depends
from fastapi.responses import Response
from core.dependencies import get_coverart_repository
from repositories.coverart_repository import CoverArtRepository

router = APIRouter(prefix="/api/covers", tags=["covers"])
log = logging.getLogger(__name__)

_ALLOWED_SIZES = {"250", "500", "1200"}
_SIZE_ALIAS_NONE = {"", "original", "full", "max", "largest"}


def _normalize_size(size: Optional[str]) -> Optional[str]:
    if size is None:
        return "500"
    normalized = size.strip().lower()
    if normalized in _SIZE_ALIAS_NONE:
        return None
    if normalized not in _ALLOWED_SIZES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported size '{size}'. Choose one of 250, 500, 1200 or original.",
        )
    return normalized


@router.get("/release-group/{release_group_id}")
async def cover_from_release_group(
    release_group_id: str = Path(..., min_length=1, description="MusicBrainz release group ID"),
    size: Optional[str] = Query(
        "500",
        description="Preferred size: 250, 500, 1200, or 'original' for full size",
    ),
):
    desired_size = _normalize_size(size)
    coverart_repo = get_coverart_repository()
    result = await coverart_repo.get_release_group_cover(release_group_id, desired_size)
    
    if result:
        image_data, content_type = result
        return Response(
            content=image_data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Cover-Source": "cover-art-archive",
            }
        )
    
    raise HTTPException(status_code=404, detail="Cover art not found")


@router.get("/release/{release_id}")
async def cover_from_release(
    release_id: str = Path(..., min_length=1, description="MusicBrainz release ID"),
    size: Optional[str] = Query(
        "500",
        description="Preferred size: 250, 500, 1200, or 'original' for full size",
    ),
):
    desired_size = _normalize_size(size)
    coverart_repo = get_coverart_repository()
    result = await coverart_repo.get_release_cover(release_id, desired_size)
    
    if result:
        image_data, content_type = result
        return Response(
            content=image_data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=31536000, immutable",
                "X-Cover-Source": "cover-art-archive",
            }
        )
    
    raise HTTPException(status_code=404, detail="Cover art not found")


@router.get("/artist/{artist_id}")
async def get_artist_cover(
    artist_id: str,
    size: Optional[int] = None,
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    result = await coverart_repo.get_artist_image(artist_id, size)
    
    if not result:
        raise HTTPException(status_code=404, detail="Artist image not found")
    
    image_data, content_type, wikidata_id = result
    return Response(
        content=image_data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Cover-Source": "wikidata",
        }
    )
