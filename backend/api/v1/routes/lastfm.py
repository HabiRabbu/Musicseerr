import logging

from fastapi import APIRouter, Depends, HTTPException

from api.v1.schemas.settings import (
    LastFmAuthTokenResponse,
    LastFmAuthSessionRequest,
    LastFmAuthSessionResponse,
    LastFmConnectionSettings,
    LASTFM_SECRET_MASK,
)
from core.dependencies import (
    get_lastfm_auth_service,
    get_lastfm_repository,
    get_preferences_service,
    clear_lastfm_dependent_caches,
)
from core.exceptions import ConfigurationError, ExternalServiceError, TokenNotAuthorizedError
from infrastructure.msgspec_fastapi import MsgSpecBody, MsgSpecRoute
from services.lastfm_auth_service import LastFmAuthService
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

router = APIRouter(route_class=MsgSpecRoute, prefix="/api/lastfm", tags=["lastfm"])


@router.post("/auth/token", response_model=LastFmAuthTokenResponse)
async def request_auth_token(
    auth_service: LastFmAuthService = Depends(get_lastfm_auth_service),
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    try:
        settings = preferences_service.get_lastfm_connection()
        if not settings.api_key or not settings.shared_secret:
            raise HTTPException(
                status_code=400,
                detail="Last.fm API key and shared secret must be configured first",
            )

        token, auth_url = await auth_service.request_token(settings.api_key)
        logger.info(
            "Last.fm auth token requested",
            extra={"step": "token_requested", "status": "success"},
        )
        return LastFmAuthTokenResponse(token=token, auth_url=auth_url)
    except HTTPException:
        raise
    except ConfigurationError as e:
        logger.warning(
            "Last.fm auth token request failed (config): %s",
            e,
            extra={"step": "token_requested", "status": "config_error"},
        )
        raise HTTPException(status_code=400, detail=str(e))
    except ExternalServiceError as e:
        logger.warning(
            "Last.fm auth token request failed (external): %s",
            e,
            extra={"step": "token_requested", "status": "external_error"},
        )
        raise HTTPException(status_code=502, detail="Failed to get token from Last.fm")
    except Exception as e:
        logger.exception(
            "Failed to request Last.fm auth token: %s",
            e,
            extra={"step": "token_requested", "status": "unexpected_error"},
        )
        raise HTTPException(status_code=500, detail="Failed to request auth token")


@router.post("/auth/session", response_model=LastFmAuthSessionResponse)
async def exchange_auth_session(
    request: LastFmAuthSessionRequest = MsgSpecBody(LastFmAuthSessionRequest),
    auth_service: LastFmAuthService = Depends(get_lastfm_auth_service),
    preferences_service: PreferencesService = Depends(get_preferences_service),
):
    try:
        username, session_key, _ = await auth_service.exchange_session(request.token)

        settings = preferences_service.get_lastfm_connection()
        updated = LastFmConnectionSettings(
            api_key=settings.api_key,
            shared_secret=settings.shared_secret,
            session_key=session_key,
            username=username,
            enabled=settings.enabled,
        )
        preferences_service.save_lastfm_connection(updated)
        get_lastfm_repository.cache_clear()
        get_lastfm_auth_service.cache_clear()
        clear_lastfm_dependent_caches()
        logger.info(
            "Last.fm session exchanged for user %s",
            username,
            extra={"step": "session_exchanged", "status": "success"},
        )

        return LastFmAuthSessionResponse(
            username=username,
            success=True,
            message=f"Successfully authorized as {username}",
        )
    except TokenNotAuthorizedError:
        message = "Token not yet authorized. Please authorize in the Last.fm tab first, then try again."
        error_code = "token_not_authorized"
        logger.warning(
            "Last.fm session exchange failed: token not authorized",
            extra={
                "step": "session_exchanged",
                "status": "token_not_authorized",
                "error_code": error_code,
            },
        )
        raise HTTPException(status_code=502, detail=message)
    except ExternalServiceError as e:
        message = "Authorization failed. Please try again."
        error_code = "external_error"
        logger.warning(
            "Last.fm session exchange failed: %s",
            e,
            extra={
                "step": "session_exchanged",
                "status": "external_error",
                "error_code": error_code,
            },
        )
        raise HTTPException(status_code=502, detail=message)
    except ConfigurationError as e:
        logger.warning(
            "Last.fm session exchange rejected: %s",
            e,
            extra={
                "step": "session_exchanged",
                "status": "configuration_error",
                "error_code": "configuration_error",
            },
        )
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception(
            "Failed to exchange Last.fm session: %s",
            e,
            extra={
                "step": "session_exchanged",
                "status": "unexpected_error",
                "error_code": "unexpected_error",
            },
        )
        raise HTTPException(status_code=500, detail="Session exchange failed unexpectedly")
