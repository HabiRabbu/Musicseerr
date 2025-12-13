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
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    desired_size = _normalize_size(size)
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
    
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
        <rect fill="#374151" width="200" height="200"/>
        <circle cx="100" cy="100" r="70" fill="#1f2937" stroke="#4B5563" stroke-width="2"/>
        <circle cx="100" cy="100" r="50" fill="none" stroke="#4B5563" stroke-width="1"/>
        <circle cx="100" cy="100" r="30" fill="none" stroke="#4B5563" stroke-width="1"/>
        <circle cx="100" cy="100" r="12" fill="#4B5563"/>
        <circle cx="100" cy="100" r="4" fill="#374151"/>
    </svg>'''
    return Response(
        content=placeholder_svg.encode(),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Cover-Source": "placeholder",
        }
    )


@router.get("/release/{release_id}")
async def cover_from_release(
    release_id: str = Path(..., min_length=1, description="MusicBrainz release ID"),
    size: Optional[str] = Query(
        "500",
        description="Preferred size: 250, 500, 1200, or 'original' for full size",
    ),
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    desired_size = _normalize_size(size)
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
    
    placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
        <rect fill="#374151" width="200" height="200"/>
        <circle cx="100" cy="100" r="70" fill="#1f2937" stroke="#4B5563" stroke-width="2"/>
        <circle cx="100" cy="100" r="50" fill="none" stroke="#4B5563" stroke-width="1"/>
        <circle cx="100" cy="100" r="30" fill="none" stroke="#4B5563" stroke-width="1"/>
        <circle cx="100" cy="100" r="12" fill="#4B5563"/>
        <circle cx="100" cy="100" r="4" fill="#374151"/>
    </svg>'''
    return Response(
        content=placeholder_svg.encode(),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": "public, max-age=86400",
            "X-Cover-Source": "placeholder",
        }
    )


@router.get("/artist/{artist_id}")
async def get_artist_cover(
    artist_id: str,
    size: Optional[int] = Query(None, description="Preferred size in pixels for width"),
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    result = await coverart_repo.get_artist_image(artist_id, size)
    
    if not result:
        placeholder_svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200">
            <rect fill="#374151" width="200" height="200"/>
            <circle cx="100" cy="80" r="30" fill="#6B7280"/>
            <path d="M60 120 Q100 140 140 120 L140 160 Q100 180 60 160 Z" fill="#6B7280"/>
        </svg>'''
        return Response(
            content=placeholder_svg.encode(),
            media_type="image/svg+xml",
            headers={
                "Cache-Control": "public, max-age=86400",
                "X-Cover-Source": "placeholder",
            }
        )
    
    image_data, content_type, wikidata_id = result
    return Response(
        content=image_data,
        media_type=content_type,
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Cover-Source": "wikidata",
        }
    )


@router.get("/debug/artist/{artist_id}")
async def debug_artist_cover(
    artist_id: str,
    coverart_repo: CoverArtRepository = Depends(get_coverart_repository)
):
    """
    Debug endpoint that returns diagnostic info about an artist image fetch.
    Shows cache state, Lidarr availability, MusicBrainz relations, and Wikidata URL.
    """
    from infrastructure.validators import validate_mbid
    
    debug_info = {
        "artist_id": artist_id,
        "is_valid_mbid": False,
        "validated_mbid": None,
        "disk_cache": {
            "exists_250": False,
            "exists_500": False,
            "meta_250": None,
            "meta_500": None,
        },
        "lidarr": {
            "configured": False,
            "has_image_url": False,
            "image_url": None,
        },
        "musicbrainz": {
            "artist_found": False,
            "has_wikidata_relation": False,
            "wikidata_url": None,
        },
        "memory_cache": {
            "wikidata_url_cached": False,
            "cached_value": None,
        },
        "recommendation": None,
    }
    
    try:
        validated_id = validate_mbid(artist_id, "artist")
        debug_info["is_valid_mbid"] = True
        debug_info["validated_mbid"] = validated_id
    except ValueError as e:
        debug_info["recommendation"] = f"Invalid MBID format: {e}. No image can be fetched."
        return debug_info
    
    debug_info = await coverart_repo.debug_artist_image(validated_id, debug_info)
    
    if debug_info["disk_cache"]["exists_250"] or debug_info["disk_cache"]["exists_500"]:
        debug_info["recommendation"] = "Image is cached on disk - should load successfully."
    elif debug_info["lidarr"]["has_image_url"]:
        debug_info["recommendation"] = "Lidarr has an image URL - fetch should succeed from Lidarr."
    elif debug_info["musicbrainz"]["has_wikidata_relation"]:
        debug_info["recommendation"] = "Wikidata URL found - fetch should succeed from Wikidata/Wikimedia."
    else:
        debug_info["recommendation"] = "No image source found. This artist will show a placeholder."
    
    return debug_info
