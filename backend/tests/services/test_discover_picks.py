"""Tests for the Discover Picks section builder in DiscoverHomepageService."""

import random

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from api.v1.schemas.discover import DiscoverResponse
from api.v1.schemas.home import HomeSection, HomeAlbum
from api.v1.schemas.settings import (
    ListenBrainzConnectionSettings,
    LastFmConnectionSettings,
    PrimaryMusicSourceSettings,
)
from repositories.listenbrainz_models import ListenBrainzReleaseGroup
from repositories.lastfm_models import LastFmArtist
from services.discover.homepage_service import (
    DiscoverHomepageService,
    DISCOVER_PICKS_CACHE_TTL,
)
from services.discover.integration_helpers import IntegrationHelpers


def _make_lb_settings(
    enabled: bool = True, username: str = "lbuser",
) -> ListenBrainzConnectionSettings:
    return ListenBrainzConnectionSettings(
        user_token="tok", username=username, enabled=enabled,
    )


def _make_lfm_settings(
    enabled: bool = True, username: str = "lfmuser",
) -> LastFmConnectionSettings:
    return LastFmConnectionSettings(
        api_key="key", shared_secret="secret", session_key="sk",
        username=username, enabled=enabled,
    )


def _make_prefs(
    lb_enabled: bool = True,
    lfm_enabled: bool = False,
    primary_source: str = "listenbrainz",
    affinity_weight: float = 0.7,
    picks_count: int = 12,
) -> MagicMock:
    prefs = MagicMock()
    prefs.get_listenbrainz_connection.return_value = _make_lb_settings(enabled=lb_enabled)
    prefs.get_lastfm_connection.return_value = _make_lfm_settings(enabled=lfm_enabled)
    prefs.is_lastfm_enabled.return_value = lfm_enabled
    prefs.get_primary_music_source.return_value = PrimaryMusicSourceSettings(source=primary_source)

    jf_settings = MagicMock()
    jf_settings.enabled = False
    jf_settings.jellyfin_url = ""
    jf_settings.api_key = ""
    prefs.get_jellyfin_connection.return_value = jf_settings

    lidarr = MagicMock()
    lidarr.lidarr_url = ""
    lidarr.lidarr_api_key = ""
    prefs.get_lidarr_connection.return_value = lidarr

    yt = MagicMock()
    yt.enabled = False
    yt.api_key = ""
    prefs.get_youtube_connection.return_value = yt

    lf = MagicMock()
    lf.enabled = False
    lf.music_path = ""
    prefs.get_local_files_connection.return_value = lf

    adv = MagicMock()
    adv.discover_queue_size = 10
    adv.discover_queue_ttl = 3600
    adv.discover_queue_seed_artists = 3
    adv.discover_queue_wildcard_slots = 2
    adv.discover_queue_similar_artists_limit = 15
    adv.discover_queue_albums_per_similar = 3
    adv.discover_queue_enrich_ttl = 3600
    adv.discover_queue_lastfm_mbid_max_lookups = 10
    adv.discover_picks_genre_affinity_weight = affinity_weight
    adv.discover_picks_count = picks_count
    prefs.get_advanced_settings.return_value = adv

    return prefs


def _make_genre_index(
    top_genres: list[tuple[str, int]] | None = None,
    genres_for_artists: dict[str, list[str]] | None = None,
) -> AsyncMock:
    genre_index = AsyncMock()
    genre_index.get_top_genres = AsyncMock(return_value=top_genres or [])
    genre_index.get_genres_for_artists = AsyncMock(return_value=genres_for_artists or {})
    return genre_index


def _make_cache() -> AsyncMock:
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


def _make_release_groups(
    count: int,
    prefix: str = "rg",
    artist_genres: dict[str, list[str]] | None = None,
) -> list[ListenBrainzReleaseGroup]:
    return [
        ListenBrainzReleaseGroup(
            release_group_name=f"Album {prefix}-{i}",
            artist_name=f"Artist {prefix}-{i}",
            listen_count=100 - i,
            release_group_mbid=f"{prefix}-mbid-{i}",
            artist_mbids=[f"artist-{prefix}-{i}"],
        )
        for i in range(count)
    ]


def _make_service(
    genre_index: AsyncMock | None = None,
    cache: AsyncMock | None = None,
    prefs: MagicMock | None = None,
    lastfm_repo: AsyncMock | None = None,
    mbid_store: AsyncMock | None = None,
) -> DiscoverHomepageService:
    lb_repo = AsyncMock()
    jf_repo = AsyncMock()
    lidarr_repo = AsyncMock()
    mb_repo = AsyncMock()
    if prefs is None:
        prefs = _make_prefs()
    integration = IntegrationHelpers(prefs)
    mbid_resolution = MagicMock()

    return DiscoverHomepageService(
        listenbrainz_repo=lb_repo,
        jellyfin_repo=jf_repo,
        lidarr_repo=lidarr_repo,
        musicbrainz_repo=mb_repo,
        integration=integration,
        mbid_resolution=mbid_resolution,
        memory_cache=cache,
        genre_index=genre_index,
        lastfm_repo=lastfm_repo,
        mbid_store=mbid_store,
    )


# ---------------------------------------------------------------------------
# Test 16 - constant value
# ---------------------------------------------------------------------------
class TestConstantValue:
    def test_discover_picks_cache_ttl_is_14400(self) -> None:
        assert DISCOVER_PICKS_CACHE_TTL == 14400


# ---------------------------------------------------------------------------
# Test 15 - cache key format
# ---------------------------------------------------------------------------
class TestCacheKeyFormat:
    def test_cache_key_format_listenbrainz(self) -> None:
        service = _make_service()
        assert service._discover_picks_cache_key("listenbrainz") == "discover_picks:listenbrainz"

    def test_cache_key_format_lastfm(self) -> None:
        service = _make_service()
        assert service._discover_picks_cache_key("lastfm") == "discover_picks:lastfm"


# ---------------------------------------------------------------------------
# Test 1 - returns None when genre_index is None
# ---------------------------------------------------------------------------
class TestReturnsNoneWhenGenreIndexIsNone:
    @pytest.mark.asyncio
    async def test_returns_none_when_genre_index_is_none(self) -> None:
        service = _make_service(genre_index=None)
        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is None


# ---------------------------------------------------------------------------
# Test 2 - returns None when candidate pool is empty
# ---------------------------------------------------------------------------
class TestReturnsNoneWhenCandidatePoolIsEmpty:
    @pytest.mark.asyncio
    async def test_returns_none_when_candidate_pool_is_empty(self) -> None:
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=[])

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is None


# ---------------------------------------------------------------------------
# Test 3 - returns None when all candidates in library
# ---------------------------------------------------------------------------
class TestReturnsNoneWhenAllCandidatesInLibrary:
    @pytest.mark.asyncio
    async def test_returns_none_when_all_candidates_in_library(self) -> None:
        candidates = _make_release_groups(5)
        library_mbids = {c.release_group_mbid.lower() for c in candidates}

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(library_mbids, "listenbrainz", True, "user")
        assert result is None


# ---------------------------------------------------------------------------
# Test 4 - returns section with correct count
# ---------------------------------------------------------------------------
class TestReturnsSectionWithCorrectCount:
    @pytest.mark.asyncio
    async def test_returns_section_with_correct_count(self) -> None:
        candidates = _make_release_groups(50)
        genre_index = _make_genre_index(
            top_genres=[("rock", 50), ("electronic", 30)],
            genres_for_artists={},
        )
        cache = _make_cache()
        prefs = _make_prefs(picks_count=12)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 12


# ---------------------------------------------------------------------------
# Test 5 - returns section with fewer when pool smaller than count
# ---------------------------------------------------------------------------
class TestReturnsSectionWithFewerWhenPoolSmaller:
    @pytest.mark.asyncio
    async def test_returns_section_with_fewer_when_pool_smaller_than_count(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(picks_count=12)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 5


# ---------------------------------------------------------------------------
# Test 6 - section type is albums
# ---------------------------------------------------------------------------
class TestSectionTypeIsAlbums:
    @pytest.mark.asyncio
    async def test_section_type_is_albums(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert result.type == "albums"


# ---------------------------------------------------------------------------
# Test 7 - section title is Discover Picks
# ---------------------------------------------------------------------------
class TestSectionTitleIsDiscoverPicks:
    @pytest.mark.asyncio
    async def test_section_title_is_discover_picks(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert result.title == "Discover Picks"


# ---------------------------------------------------------------------------
# Test 8 - section source matches resolved_source
# ---------------------------------------------------------------------------
class TestSectionSourceMatchesResolvedSource:
    @pytest.mark.asyncio
    async def test_section_source_matches_resolved_source(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "my_source", True, "user")
        assert result is not None
        assert result.source == "my_source"


# ---------------------------------------------------------------------------
# Test 9 - library mbids excluded
# ---------------------------------------------------------------------------
class TestLibraryMbidsExcluded:
    @pytest.mark.asyncio
    async def test_library_mbids_excluded(self) -> None:
        candidates = _make_release_groups(10)
        # Put the first 3 candidates in library
        library_mbids = {candidates[i].release_group_mbid.lower() for i in range(3)}

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(picks_count=20)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(library_mbids, "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 7
        result_mbids = {item.mbid.lower() for item in result.items if item.mbid}
        assert not result_mbids & library_mbids


# ---------------------------------------------------------------------------
# Test 10 - genre affinity weight 1.0 biases by genre
# ---------------------------------------------------------------------------
class TestGenreAffinityWeight1BiasesByGenre:
    @pytest.mark.asyncio
    async def test_genre_affinity_weight_1_biases_by_genre(self) -> None:
        # 6 candidates with matching genres, 6 without
        matching = _make_release_groups(6, prefix="match")
        non_matching = _make_release_groups(6, prefix="nomatch")
        all_candidates = matching + non_matching

        genres_for_artists = {}
        for c in matching:
            genres_for_artists[c.artist_mbids[0].lower()] = ["rock", "indie"]
        for c in non_matching:
            genres_for_artists[c.artist_mbids[0].lower()] = ["country", "folk"]

        genre_index = _make_genre_index(
            top_genres=[("rock", 50), ("indie", 30)],
            genres_for_artists=genres_for_artists,
        )
        cache = _make_cache()
        prefs = _make_prefs(affinity_weight=1.0, picks_count=6)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=all_candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 6
        # All top-6 should be the matching-genre candidates
        result_mbids = {item.mbid for item in result.items}
        match_mbids = {c.release_group_mbid for c in matching}
        assert result_mbids == match_mbids


# ---------------------------------------------------------------------------
# Test 11 - genre affinity weight 0.0 is fully random
# ---------------------------------------------------------------------------
class TestGenreAffinityWeight0IsFullyRandom:
    @pytest.mark.asyncio
    async def test_genre_affinity_weight_0_is_fully_random(self) -> None:
        candidates = _make_release_groups(20)
        genres_for_artists = {
            c.artist_mbids[0].lower(): ["rock"] for c in candidates[:10]
        }
        genre_index = _make_genre_index(
            top_genres=[("rock", 50)],
            genres_for_artists=genres_for_artists,
        )
        cache = _make_cache()
        prefs = _make_prefs(affinity_weight=0.0, picks_count=10)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        random.seed(42)
        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 10
        # With weight=0.0, genre overlap doesn't matter - order is random.
        # Run again with same seed to verify determinism.
        cache_second = _make_cache()
        service2 = _make_service(genre_index=genre_index, cache=cache_second, prefs=prefs)
        service2._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)
        # Reset genre_index mocks since they were consumed
        genre_index.get_top_genres = AsyncMock(return_value=[("rock", 50)])
        genre_index.get_genres_for_artists = AsyncMock(return_value=genres_for_artists)

        random.seed(42)
        result2 = await service2._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result2 is not None
        assert [item.mbid for item in result.items] == [item.mbid for item in result2.items]


# ---------------------------------------------------------------------------
# Test 12 - settings override changes count
# ---------------------------------------------------------------------------
class TestSettingsOverrideChangesCount:
    @pytest.mark.asyncio
    async def test_settings_override_changes_count(self) -> None:
        candidates = _make_release_groups(20)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(affinity_weight=0.5, picks_count=8)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 8


# ---------------------------------------------------------------------------
# Test 13 - cached result returned on second call
# ---------------------------------------------------------------------------
class TestCachedResultReturnedOnSecondCall:
    @pytest.mark.asyncio
    async def test_cached_result_returned_on_second_call(self) -> None:
        candidates = _make_release_groups(10)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(picks_count=5)
        service = _make_service(genre_index=genre_index, cache=cache, prefs=prefs)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        # First call - should fetch from LB
        result1 = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result1 is not None
        assert service._lb_repo.get_sitewide_top_release_groups.await_count == 1

        # Simulate cache returning the wrapper on second call
        cache.get = AsyncMock(return_value={"section": result1})
        result2 = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result2 is result1
        # LB repo should NOT have been called again
        assert service._lb_repo.get_sitewide_top_release_groups.await_count == 1


# ---------------------------------------------------------------------------
# Test 14 - cache TTL is 4 hours
# ---------------------------------------------------------------------------
class TestCacheTtlIs4Hours:
    @pytest.mark.asyncio
    async def test_cache_ttl_is_4_hours(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert cache.set.await_count >= 1
        # Find the call that cached the result
        for call in cache.set.call_args_list:
            args = call[0]
            if args[0] == "discover_picks:listenbrainz":
                assert args[2] == 14400
                return
        pytest.fail("cache.set was not called with discover_picks key")


# ---------------------------------------------------------------------------
# Test 17 - exception returns None
# ---------------------------------------------------------------------------
class TestExceptionReturnsNone:
    @pytest.mark.asyncio
    async def test_exception_returns_none(self) -> None:
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(
            side_effect=Exception("API failure"),
        )

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is None


# ---------------------------------------------------------------------------
# Test 18 - Last.fm path when LB disabled
# ---------------------------------------------------------------------------
class TestLastfmPathWhenLbDisabled:
    @pytest.mark.asyncio
    async def test_lastfm_path_when_lb_disabled(self) -> None:
        lfm_repo = AsyncMock()
        lfm_artists = [
            LastFmArtist(name="Artist A", mbid="lfm-artist-1"),
            LastFmArtist(name="Artist B", mbid="lfm-artist-2"),
        ]
        lfm_repo.get_global_top_artists = AsyncMock(return_value=lfm_artists)

        lb_release_groups = _make_release_groups(3, prefix="lfm-rg")

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(lb_enabled=False, lfm_enabled=True)
        service = _make_service(
            genre_index=genre_index, cache=cache, prefs=prefs, lastfm_repo=lfm_repo,
        )
        service._lb_repo.get_artist_top_release_groups = AsyncMock(
            return_value=lb_release_groups,
        )

        result = await service._build_discover_picks(set(), "lastfm", False, None)
        assert result is not None
        lfm_repo.get_global_top_artists.assert_awaited_once()
        assert len(result.items) > 0


# ---------------------------------------------------------------------------
# Test 19 - _has_meaningful_content with discover_picks
# ---------------------------------------------------------------------------
class TestHasMeaningfulContentWithDiscoverPicks:
    def test_has_meaningful_content_with_discover_picks(self) -> None:
        service = _make_service()
        response = DiscoverResponse(
            discover_picks=HomeSection(
                title="Discover Picks",
                type="albums",
                items=[HomeAlbum(name="A", mbid="m1", artist_name="Art")],
                source="listenbrainz",
            ),
        )
        assert service._has_meaningful_content(response) is True

    def test_has_meaningful_content_false_when_empty(self) -> None:
        service = _make_service()
        response = DiscoverResponse()
        assert service._has_meaningful_content(response) is False


# ---------------------------------------------------------------------------
# Test 20 - wired into build_discover_data
# ---------------------------------------------------------------------------
class TestWiredIntoBuildDiscoverData:
    @pytest.mark.asyncio
    async def test_wired_into_build_discover_data(self) -> None:
        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)

        # Wire up minimal mocks for build_discover_data
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(
            return_value=candidates,
        )
        service._lb_repo.get_user_top_artists = AsyncMock(return_value=[])
        service._lb_repo.get_user_fresh_releases = AsyncMock(return_value=[])
        service._lb_repo.get_user_genre_activity = AsyncMock(return_value=[])
        service._lb_repo.get_similar_artists = AsyncMock(return_value=[])
        service._lb_repo.get_sitewide_top_artists = AsyncMock(return_value=[])
        service._jf_repo.get_most_played_artists = AsyncMock(return_value=[])
        service._mbid.get_library_artist_mbids = AsyncMock(return_value=set())

        response = await service.build_discover_data(source="listenbrainz")
        assert response.discover_picks is not None
        assert response.discover_picks.title == "Discover Picks"


# ---------------------------------------------------------------------------
# Test 21 - ignored MBIDs are filtered out
# ---------------------------------------------------------------------------
class TestIgnoredMbidsAreFilteredOut:
    @pytest.mark.asyncio
    async def test_ignored_mbids_are_filtered_out(self) -> None:
        candidates = _make_release_groups(10)
        # Mark 2 candidates as ignored
        ignored_mbids = {
            candidates[0].release_group_mbid.lower(),
            candidates[1].release_group_mbid.lower(),
        }

        mbid_store = AsyncMock()
        mbid_store.get_ignored_release_mbids = AsyncMock(return_value=ignored_mbids)

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(picks_count=20)
        service = _make_service(
            genre_index=genre_index, cache=cache, prefs=prefs, mbid_store=mbid_store,
        )
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        assert len(result.items) == 8
        result_mbids = {item.mbid.lower() for item in result.items if item.mbid}
        assert not result_mbids & ignored_mbids


# ---------------------------------------------------------------------------
# Test 22 - Last.fm path when source is lastfm (even if LB is enabled)
# ---------------------------------------------------------------------------
class TestLastfmPathWhenSourceIsLastfm:
    @pytest.mark.asyncio
    async def test_lastfm_source_uses_lfm_repo_when_lb_also_enabled(self) -> None:
        lfm_repo = AsyncMock()
        lfm_artists = [
            LastFmArtist(name="Artist A", mbid="lfm-artist-1"),
        ]
        lfm_repo.get_global_top_artists = AsyncMock(return_value=lfm_artists)

        lb_release_groups = _make_release_groups(3, prefix="lfm-rg")

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(lb_enabled=True, lfm_enabled=True)
        service = _make_service(
            genre_index=genre_index, cache=cache, prefs=prefs, lastfm_repo=lfm_repo,
        )
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=[])
        service._lb_repo.get_artist_top_release_groups = AsyncMock(
            return_value=lb_release_groups,
        )

        result = await service._build_discover_picks(set(), "lastfm", True, None)
        assert result is not None
        lfm_repo.get_global_top_artists.assert_awaited_once()
        # LB sitewide should NOT have been called since source is lastfm
        service._lb_repo.get_sitewide_top_release_groups.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_listenbrainz_source_uses_lb_repo(self) -> None:
        lfm_repo = AsyncMock()

        candidates = _make_release_groups(5)
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        prefs = _make_prefs(lb_enabled=True, lfm_enabled=True)
        service = _make_service(
            genre_index=genre_index, cache=cache, prefs=prefs, lastfm_repo=lfm_repo,
        )
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is not None
        service._lb_repo.get_sitewide_top_release_groups.assert_awaited_once()
        # LFM repo should NOT have been called since source is listenbrainz
        lfm_repo.get_global_top_artists.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ignored_mbid_store_failure_logs_and_continues(self) -> None:
        candidates = _make_release_groups(5)

        mbid_store = AsyncMock()
        mbid_store.get_ignored_release_mbids = AsyncMock(side_effect=Exception("DB down"))

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(
            genre_index=genre_index, cache=cache, mbid_store=mbid_store,
        )
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        # Should still succeed - ignored filtering is best-effort
        assert result is not None
        assert len(result.items) == 5


# ---------------------------------------------------------------------------
# Test 22 - negative result is cached and reused
# ---------------------------------------------------------------------------
class TestNegativeResultIsCachedAndReused:
    @pytest.mark.asyncio
    async def test_negative_result_is_cached_and_reused(self) -> None:
        """When all candidates are filtered out, None is cached. Second call returns None without re-fetching."""
        candidates = _make_release_groups(3)
        library_mbids = {c.release_group_mbid.lower() for c in candidates}

        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=candidates)

        # First call - all filtered, should cache None
        result1 = await service._build_discover_picks(library_mbids, "listenbrainz", True, "user")
        assert result1 is None
        assert service._lb_repo.get_sitewide_top_release_groups.await_count == 1

        # Simulate cache returning the wrapper on second call
        cache.get = AsyncMock(return_value={"section": None})
        result2 = await service._build_discover_picks(library_mbids, "listenbrainz", True, "user")
        assert result2 is None
        # LB repo should NOT have been called again
        assert service._lb_repo.get_sitewide_top_release_groups.await_count == 1

    @pytest.mark.asyncio
    async def test_empty_candidates_are_cached(self) -> None:
        """When candidate pool is empty, None is cached."""
        genre_index = _make_genre_index(top_genres=[("rock", 10)])
        cache = _make_cache()
        service = _make_service(genre_index=genre_index, cache=cache)
        service._lb_repo.get_sitewide_top_release_groups = AsyncMock(return_value=[])

        result = await service._build_discover_picks(set(), "listenbrainz", True, "user")
        assert result is None
        # Verify cache.set was called with the wrapper
        cache.set.assert_awaited()
        set_calls = [
            c for c in cache.set.call_args_list
            if c[0][0] == "discover_picks:listenbrainz"
        ]
        assert len(set_calls) == 1
        assert set_calls[0][0][1] == {"section": None}
