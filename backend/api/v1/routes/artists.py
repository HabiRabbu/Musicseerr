import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from core.exceptions import ClientDisconnectedError, ExternalServiceError
from api.v1.schemas.artist import ArtistInfo, ArtistExtendedInfo, ArtistReleases, LastFmArtistEnrichment, ArtistMonitoringRequest, ArtistMonitoringResponse, ArtistMonitoringStatus
from api.v1.schemas.discovery import SimilarArtistsResponse, TopSongsResponse, TopAlbumsResponse
from core.dependencies import get_artist_service, get_artist_discovery_service, get_artist_enrichment_service
from services.artist_service import ArtistService
from services.artist_discovery_service import ArtistDiscoveryService
from services.artist_enrichment_service import ArtistEnrichmentService
from infrastructure.validators import is_unknown_mbid, validate_mbid
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from infrastructure.degradation import try_get_degradation_context

import msgspec.structs

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/artists", tags=["artist"])


@router.get("/{artist_id}", response_model=ArtistInfo)
async def get_artist(
    artist_id: str,
    request: Request,
    artist_service: ArtistService = Depends(get_artist_service)
):
    if await request.is_disconnected():
        raise ClientDisconnectedError("Client disconnected")
    
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        result = await artist_service.get_artist_info_basic(artist_id)
        ctx = try_get_degradation_context()
        if ctx and ctx.has_degradation():
            result = msgspec.structs.replace(result, service_status=ctx.degraded_summary())
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artist request"
        )


@router.get("/{artist_id}/extended", response_model=ArtistExtendedInfo)
async def get_artist_extended(
    artist_id: str,
    artist_service: ArtistService = Depends(get_artist_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        return await artist_service.get_artist_extended_info(artist_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artist request"
        )


@router.get("/{artist_id}/releases", response_model=ArtistReleases)
async def get_artist_releases(
    artist_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    artist_service: ArtistService = Depends(get_artist_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    
    try:
        return await artist_service.get_artist_releases(artist_id, offset, limit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artist request"
        )


@router.get("/{artist_id}/similar", response_model=SimilarArtistsResponse)
async def get_similar_artists(
    artist_id: str,
    count: int = Query(default=15, ge=1, le=50),
    source: Literal["listenbrainz", "lastfm"] | None = Query(default=None, description="Data source: listenbrainz or lastfm"),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_similar_artists(artist_id, count, source=source)


@router.get("/{artist_id}/top-songs", response_model=TopSongsResponse)
async def get_top_songs(
    artist_id: str,
    count: int = Query(default=10, ge=1, le=50),
    source: Literal["listenbrainz", "lastfm"] | None = Query(default=None, description="Data source: listenbrainz or lastfm"),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_top_songs(artist_id, count, source=source)


@router.get("/{artist_id}/top-albums", response_model=TopAlbumsResponse)
async def get_top_albums(
    artist_id: str,
    count: int = Query(default=10, ge=1, le=50),
    source: Literal["listenbrainz", "lastfm"] | None = Query(default=None, description="Data source: listenbrainz or lastfm"),
    discovery_service: ArtistDiscoveryService = Depends(get_artist_discovery_service)
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    return await discovery_service.get_top_albums(artist_id, count, source=source)


@router.get("/{artist_id}/lastfm", response_model=LastFmArtistEnrichment)
async def get_artist_lastfm_enrichment(
    artist_id: str,
    artist_name: str = Query(..., description="Artist name for Last.fm lookup"),
    enrichment_service: ArtistEnrichmentService = Depends(get_artist_enrichment_service),
):
    if is_unknown_mbid(artist_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or unknown artist ID: {artist_id}"
        )
    result = await enrichment_service.get_lastfm_enrichment(artist_id, artist_name)
    if result is None:
        return LastFmArtistEnrichment()
    return result


@router.get("/{artist_id}/monitoring", response_model=ArtistMonitoringStatus)
async def get_artist_monitoring_status(
    artist_id: str,
    artist_service: ArtistService = Depends(get_artist_service),
):
    try:
        validate_mbid(artist_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artist ID",
        )
    try:
        return await artist_service.get_artist_monitoring_status(artist_id)
    except Exception:
        logger.debug("Failed to fetch monitoring status for %s", artist_id, exc_info=True)
        return ArtistMonitoringStatus(in_lidarr=False, monitored=False, auto_download=False)


@router.put("/{artist_id}/monitoring", response_model=ArtistMonitoringResponse)
async def update_artist_monitoring(
    artist_id: str,
    body: ArtistMonitoringRequest = MsgSpecBody(ArtistMonitoringRequest),
    artist_service: ArtistService = Depends(get_artist_service),
):
    try:
        validate_mbid(artist_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artist MBID format",
        )
    try:
        result = await artist_service.set_artist_monitoring(
            artist_id, monitored=body.monitored, auto_download=body.auto_download,
        )
        return ArtistMonitoringResponse(
            success=True,
            monitored=result.get("monitored", body.monitored),
            auto_download=result.get("auto_download", False),
        )
    except ExternalServiceError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not update monitoring. The music server returned an error.",
        )
    except Exception:
        logger.exception("Failed to update artist monitoring for %s", artist_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update monitoring status",
        )
