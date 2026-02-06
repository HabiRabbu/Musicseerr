import asyncio
import logging
from typing import Optional
from api.v1.schemas.search import ArtistEnrichment, AlbumEnrichment, EnrichmentResponse
from repositories.protocols import MusicBrainzRepositoryProtocol, ListenBrainzRepositoryProtocol
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

MAX_ENRICHMENT = 10


class SearchEnrichmentService:
    def __init__(
        self,
        mb_repo: MusicBrainzRepositoryProtocol,
        lb_repo: ListenBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
    ):
        self._mb_repo = mb_repo
        self._lb_repo = lb_repo
        self._preferences_service = preferences_service

    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences_service.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)

    async def enrich(
        self,
        artist_mbids: list[str],
        album_mbids: list[str],
    ) -> EnrichmentResponse:
        lb_enabled = self._is_listenbrainz_enabled()

        artist_mbids = artist_mbids[:MAX_ENRICHMENT]
        album_mbids = album_mbids[:MAX_ENRICHMENT]

        artist_tasks = [
            self._enrich_artist(mbid, lb_enabled)
            for mbid in artist_mbids
        ]

        album_listen_counts: dict[str, int] = {}
        if lb_enabled and album_mbids:
            try:
                album_listen_counts = await self._lb_repo.get_release_group_popularity_batch(album_mbids)
            except Exception as e:
                logger.debug(f"Failed to get album popularity batch: {e}")

        artist_results = await asyncio.gather(*artist_tasks, return_exceptions=True)

        artists: list[ArtistEnrichment] = []
        for result in artist_results:
            if isinstance(result, Exception):
                logger.debug(f"Artist enrichment failed: {result}")
                continue
            if result:
                artists.append(result)

        albums: list[AlbumEnrichment] = []
        for mbid in album_mbids:
            albums.append(AlbumEnrichment(
                musicbrainz_id=mbid,
                track_count=None,
                listen_count=album_listen_counts.get(mbid),
            ))

        return EnrichmentResponse(
            artists=artists,
            albums=albums,
            listenbrainz_enabled=lb_enabled,
        )

    async def _enrich_artist(
        self,
        mbid: str,
        fetch_lb: bool,
    ) -> Optional[ArtistEnrichment]:
        release_count: Optional[int] = None
        listen_count: Optional[int] = None

        try:
            _, total_count = await self._mb_repo.get_artist_release_groups(
                artist_mbid=mbid,
                offset=0,
                limit=1,
            )
            release_count = total_count
        except Exception as e:
            logger.debug(f"Failed to get release count for artist {mbid}: {e}")

        if fetch_lb:
            try:
                top_releases = await self._lb_repo.get_artist_top_release_groups(mbid, count=5)
                if top_releases:
                    listen_count = sum(r.listen_count for r in top_releases)
            except Exception as e:
                logger.debug(f"Failed to get LB popularity for artist {mbid}: {e}")

        return ArtistEnrichment(
            musicbrainz_id=mbid,
            release_group_count=release_count,
            listen_count=listen_count,
        )
