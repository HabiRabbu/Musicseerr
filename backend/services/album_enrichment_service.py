import logging
from typing import Optional

from api.v1.schemas.album import LastFmAlbumEnrichment
from api.v1.schemas.common import LastFmTagSchema
from infrastructure.validators import clean_lastfm_bio
from repositories.protocols import LastFmRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)


class AlbumEnrichmentService:
    def __init__(
        self,
        lastfm_repo: LastFmRepositoryProtocol,
        preferences_service: PreferencesService,
    ):
        self._lastfm_repo = lastfm_repo
        self._preferences_service = preferences_service

    async def get_lastfm_enrichment(
        self,
        artist_name: str,
        album_name: str,
        album_mbid: Optional[str] = None,
    ) -> Optional[LastFmAlbumEnrichment]:
        if not self._preferences_service.is_lastfm_enabled():
            return None

        try:
            info = await self._lastfm_repo.get_album_info(
                artist=artist_name, album=album_name, mbid=album_mbid
            )
            if info is None:
                return None

            tags = [
                LastFmTagSchema(name=t.name, url=t.url or None)
                for t in (info.tags or [])
            ]

            return LastFmAlbumEnrichment(
                summary=clean_lastfm_bio(info.summary) or None,
                tags=tags,
                listeners=info.listeners,
                playcount=info.playcount,
                url=info.url or None,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch Last.fm enrichment for album %s: %s",
                album_name,
                e,
            )
            return None
