import logging

from fastapi import APIRouter, Depends, HTTPException

from api.v1.schemas.scrobble import (
    NowPlayingRequest,
    ScrobbleRequest,
    ScrobbleResponse,
)
from core.dependencies import get_scrobble_service
from core.exceptions import ConfigurationError, ExternalServiceError
from services.scrobble_service import ScrobbleService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scrobble", tags=["scrobble"])


@router.post("/now-playing", response_model=ScrobbleResponse)
async def report_now_playing(
    request: NowPlayingRequest,
    scrobble_service: ScrobbleService = Depends(get_scrobble_service),
) -> ScrobbleResponse:
    try:
        return await scrobble_service.report_now_playing(request)
    except ConfigurationError as e:
        logger.warning("Scrobble now-playing config error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        logger.warning("Scrobble now-playing service error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in now-playing: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/submit", response_model=ScrobbleResponse)
async def submit_scrobble(
    request: ScrobbleRequest,
    scrobble_service: ScrobbleService = Depends(get_scrobble_service),
) -> ScrobbleResponse:
    try:
        return await scrobble_service.submit_scrobble(request)
    except ConfigurationError as e:
        logger.warning("Scrobble submit config error: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        logger.warning("Scrobble submit service error: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in scrobble submit: %s", e)
        raise HTTPException(status_code=500, detail="Internal server error")
