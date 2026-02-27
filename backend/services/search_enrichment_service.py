import asyncio
import logging
from typing import Optional
from api.v1.schemas.search import (
    ArtistEnrichment,
    AlbumEnrichment,
    EnrichmentBatchRequest,
    EnrichmentResponse,
    EnrichmentSource,
)
from repositories.protocols import (
    MusicBrainzRepositoryProtocol,
    ListenBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from services.preferences_service import PreferencesService

logger = logging.getLogger(__name__)

MAX_ENRICHMENT = 10


class SearchEnrichmentService:
    def __init__(
        self,
        mb_repo: MusicBrainzRepositoryProtocol,
        lb_repo: ListenBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
        lastfm_repo: Optional[LastFmRepositoryProtocol] = None,
    ):
        self._mb_repo = mb_repo
        self._lb_repo = lb_repo
        self._preferences_service = preferences_service
        self._lastfm_repo = lastfm_repo

    def _is_listenbrainz_enabled(self) -> bool:
        lb_settings = self._preferences_service.get_listenbrainz_connection()
        return lb_settings.enabled and bool(lb_settings.username)

    def _is_lastfm_enabled(self) -> bool:
        try:
            lfm_settings = self._preferences_service.get_lastfm_connection()
            return lfm_settings.enabled and bool(lfm_settings.api_key)
        except Exception:
            return False

    def _get_enrichment_source(self) -> EnrichmentSource:
        lb_enabled = self._is_listenbrainz_enabled()
        lfm_enabled = self._is_lastfm_enabled() and self._lastfm_repo is not None

        if not lb_enabled and not lfm_enabled:
            return "none"

        try:
            primary = self._preferences_service.get_primary_music_source()
            preferred = primary.source
        except Exception:
            preferred = "listenbrainz"

        if preferred == "lastfm" and lfm_enabled:
            return "lastfm"
        if preferred == "listenbrainz" and lb_enabled:
            return "listenbrainz"
        if lb_enabled:
            return "listenbrainz"
        if lfm_enabled:
            return "lastfm"
        return "none"

    async def enrich(
        self,
        artist_mbids: list[str],
        album_mbids: list[str],
    ) -> EnrichmentResponse:
        source = self._get_enrichment_source()

        artist_mbids = artist_mbids[:MAX_ENRICHMENT]
        album_mbids = album_mbids[:MAX_ENRICHMENT]

        artist_tasks = [
            self._enrich_artist(mbid, source)
            for mbid in artist_mbids
        ]

        album_listen_counts: dict[str, int] = {}
        if source == "listenbrainz" and album_mbids:
            try:
                album_listen_counts = await self._lb_repo.get_release_group_popularity_batch(
                    album_mbids
                )
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
            source=source,
        )

    async def enrich_batch(self, request: EnrichmentBatchRequest) -> EnrichmentResponse:
        source = self._get_enrichment_source()

        artist_requests = request.artists[:MAX_ENRICHMENT]
        album_requests = request.albums[:MAX_ENRICHMENT]

        artist_tasks = [
            self._enrich_artist(req.musicbrainz_id, source, name=req.name)
            for req in artist_requests
        ]

        album_tasks: list[asyncio.Task[AlbumEnrichment]] = []
        album_listen_counts: dict[str, int] = {}

        if source == "listenbrainz" and album_requests:
            mbids = [r.musicbrainz_id for r in album_requests]
            try:
                album_listen_counts = await self._lb_repo.get_release_group_popularity_batch(mbids)
            except Exception as e:
                logger.debug(f"Failed to get album popularity batch: {e}")
        elif source == "lastfm" and album_requests and self._lastfm_repo:
            album_tasks = [
                self._enrich_album_lastfm(req.musicbrainz_id, req.artist_name, req.album_name)
                for req in album_requests
            ]

        artist_results = await asyncio.gather(*artist_tasks, return_exceptions=True)

        artists: list[ArtistEnrichment] = []
        for result in artist_results:
            if isinstance(result, Exception):
                logger.debug(f"Artist enrichment failed: {result}")
                continue
            if result:
                artists.append(result)

        albums: list[AlbumEnrichment] = []
        if album_tasks:
            album_results = await asyncio.gather(*album_tasks, return_exceptions=True)
            for result in album_results:
                if isinstance(result, Exception):
                    logger.debug(f"Album enrichment failed: {result}")
                    continue
                if result:
                    albums.append(result)
        else:
            for req in album_requests:
                albums.append(AlbumEnrichment(
                    musicbrainz_id=req.musicbrainz_id,
                    track_count=None,
                    listen_count=album_listen_counts.get(req.musicbrainz_id),
                ))

        return EnrichmentResponse(
            artists=artists,
            albums=albums,
            source=source,
        )

    async def _enrich_artist(
        self,
        mbid: str,
        source: EnrichmentSource,
        name: str = "",
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

        if source == "listenbrainz":
            try:
                top_releases = await self._lb_repo.get_artist_top_release_groups(mbid, count=5)
                if top_releases:
                    listen_count = sum(r.listen_count for r in top_releases)
            except Exception as e:
                logger.debug(f"Failed to get LB popularity for artist {mbid}: {e}")
        elif source == "lastfm" and self._lastfm_repo and name:
            try:
                info = await self._lastfm_repo.get_artist_info(artist=name, mbid=mbid)
                if info and info.listeners is not None:
                    listen_count = info.listeners
            except Exception as e:
                logger.debug(f"Failed to get Last.fm info for artist {name}: {e}")

        return ArtistEnrichment(
            musicbrainz_id=mbid,
            release_group_count=release_count,
            listen_count=listen_count,
        )

    async def _enrich_album_lastfm(
        self,
        mbid: str,
        artist_name: str,
        album_name: str,
    ) -> AlbumEnrichment:
        listen_count: Optional[int] = None

        if self._lastfm_repo and artist_name and album_name:
            try:
                info = await self._lastfm_repo.get_album_info(
                    artist=artist_name, album=album_name, mbid=mbid
                )
                if info and info.playcount is not None:
                    listen_count = info.playcount
            except Exception as e:
                logger.debug(f"Failed to get Last.fm info for album {album_name}: {e}")

        return AlbumEnrichment(
            musicbrainz_id=mbid,
            track_count=None,
            listen_count=listen_count,
        )
