"""Thin facade preserving the original DiscoverService public API.

All business logic lives in sub-services under ``services.discover.*``.
This class assembles them and delegates every public method call.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import HTTPException

from api.v1.schemas.discover import (
    DiscoverQueueEnrichment,
    DiscoverQueueResponse,
    DiscoverIgnoredRelease,
    PlaylistSuggestionsRequest,
    PlaylistSuggestionsResponse,
)
from api.v1.schemas.home import DiscoverPreview
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.persistence import LibraryDB, MBIDStore
from repositories.protocols import (
    ListenBrainzRepositoryProtocol,
    JellyfinRepositoryProtocol,
    LidarrRepositoryProtocol,
    MusicBrainzRepositoryProtocol,
    LastFmRepositoryProtocol,
)
from api.v1.schemas.home import HomeSection
from services.discover.enrichment_service import QueueEnrichmentService
from services.discover.homepage_service import DiscoverHomepageService
from services.discover.integration_helpers import IntegrationHelpers
from services.discover.mbid_resolution_service import MbidResolutionService
from services.discover.queue_service import DiscoverQueueService
from services.discover.radio_service import DiscoverRadioService
from services.preferences_service import PreferencesService


class DiscoverService:
    """Drop-in replacement for the original monolith.

    Constructor signature is identical to the old class so that
    ``dependencies.py`` needs only an import-path change.
    """

    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepositoryProtocol,
        jellyfin_repo: JellyfinRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        preferences_service: PreferencesService,
        memory_cache: CacheInterface | None = None,
        library_db: LibraryDB | None = None,
        mbid_store: MBIDStore | None = None,
        wikidata_repo: Any = None,
        lastfm_repo: LastFmRepositoryProtocol | None = None,
        audiodb_image_service: Any = None,
        genre_index: Any = None,
        radio_service: Any = None,
        playlist_service: Any = None,
    ):
        self._integration = IntegrationHelpers(preferences_service)

        self._mbid_resolution = MbidResolutionService(
            musicbrainz_repo=musicbrainz_repo,
            lidarr_repo=lidarr_repo,
            listenbrainz_repo=listenbrainz_repo,
            library_db=library_db,
            mbid_store=mbid_store,
        )

        self._enrichment = QueueEnrichmentService(
            musicbrainz_repo=musicbrainz_repo,
            listenbrainz_repo=listenbrainz_repo,
            preferences_service=preferences_service,
            integration=self._integration,
            memory_cache=memory_cache,
            wikidata_repo=wikidata_repo,
            lastfm_repo=lastfm_repo,
        )

        self._queue = DiscoverQueueService(
            listenbrainz_repo=listenbrainz_repo,
            jellyfin_repo=jellyfin_repo,
            musicbrainz_repo=musicbrainz_repo,
            integration=self._integration,
            mbid_resolution=self._mbid_resolution,
            library_db=library_db,
            mbid_store=mbid_store,
            lastfm_repo=lastfm_repo,
        )

        self._homepage = DiscoverHomepageService(
            listenbrainz_repo=listenbrainz_repo,
            jellyfin_repo=jellyfin_repo,
            lidarr_repo=lidarr_repo,
            musicbrainz_repo=musicbrainz_repo,
            integration=self._integration,
            mbid_resolution=self._mbid_resolution,
            memory_cache=memory_cache,
            lastfm_repo=lastfm_repo,
            audiodb_image_service=audiodb_image_service,
            genre_index=genre_index,
            mbid_store=mbid_store,
        )

        self._radio = radio_service
        self._playlist_service = playlist_service

    async def get_discover_data(self, source: str | None = None):
        return await self._homepage.get_discover_data(source)

    async def get_discover_preview(self) -> DiscoverPreview | None:
        return await self._homepage.get_discover_preview()

    async def refresh_discover_data(self) -> None:
        return await self._homepage.refresh_discover_data()

    async def warm_cache(self, source: str | None = None) -> None:
        return await self._homepage.warm_cache(source)

    async def build_discover_data(self, source: str | None = None):
        return await self._homepage.build_discover_data(source)

    async def generate_radio(self, request: Any) -> HomeSection:
        if self._radio is None:
            raise HTTPException(status_code=501, detail="Radio service not configured")
        return await self._radio.generate_radio(request)

    async def get_playlist_suggestions(
        self, request: PlaylistSuggestionsRequest,
    ) -> PlaylistSuggestionsResponse:
        profile = await self._playlist_service.analyse_playlist_profile(
            request.playlist_id,
        )
        if profile is None:
            raise HTTPException(status_code=404, detail="Playlist not found")
        if not profile.artist_mbids:
            raise HTTPException(status_code=422, detail="This playlist has no artist data to base suggestions on")
        section = await self._homepage.build_playlist_suggestions(
            profile, request.count, request.source,
        )
        return PlaylistSuggestionsResponse(
            suggestions=section,
            playlist_id=request.playlist_id,
            profile=profile,
        )

    async def build_queue(self, count: int | None = None, source: str | None = None) -> DiscoverQueueResponse:
        return await self._queue.build_queue(count, source)

    async def validate_queue_mbids(self, mbids: list[str]) -> list[str]:
        return await self._queue.validate_queue_mbids(mbids)

    async def ignore_release(
        self, release_group_mbid: str, artist_mbid: str, release_name: str, artist_name: str
    ) -> None:
        return await self._queue.ignore_release(release_group_mbid, artist_mbid, release_name, artist_name)

    async def get_ignored_releases(self) -> list[DiscoverIgnoredRelease]:
        return await self._queue.get_ignored_releases()

    async def enrich_queue_item(self, release_group_mbid: str) -> DiscoverQueueEnrichment:
        return await self._enrichment.enrich_queue_item(release_group_mbid)


    def resolve_source(self, source: str | None) -> str:
        return self._integration.resolve_source(source)
