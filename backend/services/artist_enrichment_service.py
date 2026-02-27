import logging
from typing import Optional

from api.v1.schemas.artist import (
    LastFmArtistEnrichment,
    LastFmSimilarArtistSchema,
)
from api.v1.schemas.common import LastFmTagSchema
from infrastructure.validators import clean_lastfm_bio
from repositories.protocols import LastFmRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)


class ArtistEnrichmentService:
    def __init__(
        self,
        lastfm_repo: LastFmRepositoryProtocol,
        preferences_service: PreferencesService,
    ):
        self._lastfm_repo = lastfm_repo
        self._preferences_service = preferences_service

    async def get_lastfm_enrichment(
        self, artist_mbid: str, artist_name: str
    ) -> Optional[LastFmArtistEnrichment]:
        if not self._preferences_service.is_lastfm_enabled():
            return None

        try:
            info = await self._lastfm_repo.get_artist_info(
                artist=artist_name, mbid=artist_mbid
            )
            if info is None:
                return None

            tags = [
                LastFmTagSchema(name=t.name, url=t.url or None)
                for t in (info.tags or [])
            ]
            similar = [
                LastFmSimilarArtistSchema(
                    name=s.name,
                    mbid=s.mbid,
                    match=s.match,
                    url=s.url or None,
                )
                for s in (info.similar or [])
            ]

            return LastFmArtistEnrichment(
                bio=clean_lastfm_bio(info.bio_summary) or None,
                summary=None,
                tags=tags,
                listeners=info.listeners,
                playcount=info.playcount,
                similar_artists=similar,
                url=info.url or None,
            )
        except Exception as e:
            logger.warning(
                "Failed to fetch Last.fm enrichment for artist %s: %s",
                artist_mbid[:8],
                e,
            )
            return None
