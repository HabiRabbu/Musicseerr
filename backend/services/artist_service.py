import asyncio
import logging
from typing import Any, Optional
from api.v1.schemas.artist import ArtistInfo, ArtistExtendedInfo, ArtistReleases, ExternalLink
from repositories.protocols import MusicBrainzRepositoryProtocol, LidarrRepositoryProtocol, WikidataRepositoryProtocol
from services.preferences_service import PreferencesService
from services.artist_utils import (
    detect_platform,
    extract_tags,
    extract_aliases,
    extract_life_span,
    extract_external_links,
    categorize_release_groups,
    categorize_lidarr_albums,
    extract_wiki_info,
    build_base_artist_info,
)
from infrastructure.cache.memory_cache import CacheInterface
from infrastructure.cache.disk_cache import DiskMetadataCache
from infrastructure.validators import validate_mbid
from core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)


class ArtistService:
    def __init__(
        self,
        mb_repo: MusicBrainzRepositoryProtocol,
        lidarr_repo: LidarrRepositoryProtocol,
        wikidata_repo: WikidataRepositoryProtocol,
        preferences_service: PreferencesService,
        memory_cache: CacheInterface,
        disk_cache: DiskMetadataCache
    ):
        self._mb_repo = mb_repo
        self._lidarr_repo = lidarr_repo
        self._wikidata_repo = wikidata_repo
        self._preferences_service = preferences_service
        self._cache = memory_cache
        self._disk_cache = disk_cache
    
    async def get_artist_info(
        self,
        artist_id: str,
        library_artist_mbids: set[str] = None,
        library_album_mbids: dict[str, Any] = None
    ) -> ArtistInfo:
        try:
            artist_id = validate_mbid(artist_id, "artist")
        except ValueError as e:
            logger.error(f"Invalid artist MBID: {e}")
            raise
        try:
            cached = await self._get_cached_artist(artist_id)
            if cached:
                return cached
            lidarr_artist = await self._lidarr_repo.get_artist_details(artist_id)
            in_library = lidarr_artist is not None and lidarr_artist.get("monitored", False)
            if in_library and lidarr_artist:
                logger.info(f"Using Lidarr as primary source for artist {artist_id[:8]}")
                artist_info = await self._build_artist_from_lidarr(artist_id, lidarr_artist, library_album_mbids)
            else:
                logger.info(f"Using MusicBrainz as primary source for artist {artist_id[:8]}")
                artist_info = await self._build_artist_from_musicbrainz(artist_id, library_artist_mbids, library_album_mbids)
            await self._save_artist_to_cache(artist_id, artist_info)
            return artist_info
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"API call failed for artist {artist_id}: {e}")
            raise ResourceNotFoundError(f"Failed to get artist info: {e}")
    
    async def _build_artist_from_lidarr(
        self,
        artist_id: str,
        lidarr_artist: dict[str, Any],
        library_album_mbids: dict[str, Any] = None
    ) -> ArtistInfo:
        description = lidarr_artist.get("overview")
        image = lidarr_artist.get("poster_url")
        fanart_url = lidarr_artist.get("fanart_url")
        banner_url = lidarr_artist.get("banner_url")

        genres = lidarr_artist.get("genres", [])
        
        external_links = []
        for link in lidarr_artist.get("links", []):
            link_name = link.get("name", "")
            link_url = link.get("url", "")
            if link_url:
                label = detect_platform(link_url, link_name.lower())
                external_links.append(ExternalLink(type=link_name.lower(), url=link_url, label=label))
        
        if library_album_mbids is None:
            library_album_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
        
        lidarr_albums = await self._lidarr_repo.get_artist_albums(artist_id)
        albums, singles, eps = self._categorize_lidarr_albums(lidarr_albums, library_album_mbids)
        
        need_musicbrainz = not description or not genres or not external_links
        aliases = []
        life_span = None
        artist_type = lidarr_artist.get("artist_type")
        disambiguation = lidarr_artist.get("disambiguation")
        country = None
        release_group_count = len(lidarr_albums)
        
        if need_musicbrainz:
            logger.debug(f"Fetching supplementary data from MusicBrainz for artist {artist_id[:8]}")
            try:
                mb_artist = await self._mb_repo.get_artist_by_id(artist_id)
                if mb_artist:
                    if not description:
                        mb_description, _ = await self._fetch_wikidata_info(mb_artist)
                        description = mb_description
                    
                    if not genres:
                        genres = extract_tags(mb_artist)

                    if not external_links:
                        external_links = self._build_external_links(mb_artist)

                    aliases = extract_aliases(mb_artist)
                    life_span = extract_life_span(mb_artist)
                    country = mb_artist.get("country")
                    
                    if not artist_type:
                        artist_type = mb_artist.get("type")
                    if not disambiguation:
                        disambiguation = mb_artist.get("disambiguation")
                    
                    release_group_count = mb_artist.get("release-group-count", release_group_count)
            except Exception as e:
                logger.warning(f"MusicBrainz fallback failed for artist {artist_id[:8]}: {e}")
        
        return ArtistInfo(
            name=lidarr_artist.get("name", "Unknown Artist"),
            musicbrainz_id=artist_id,
            disambiguation=disambiguation,
            type=artist_type,
            country=country,
            life_span=life_span,
            description=description,
            image=image,
            fanart_url=fanart_url,
            banner_url=banner_url,
            tags=genres,
            aliases=aliases,
            external_links=external_links,
            in_library=True,
            albums=albums,
            singles=singles,
            eps=eps,
            release_group_count=release_group_count,
        )
    
    def _categorize_lidarr_albums(
        self,
        lidarr_albums: list[dict[str, Any]],
        library_album_mbids: set[str]
    ) -> tuple[list[dict], list[dict], list[dict]]:
        prefs = self._preferences_service.get_preferences()
        included_primary_types = set(t.lower() for t in prefs.primary_types)
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        return categorize_lidarr_albums(lidarr_albums, included_primary_types, included_secondary_types)
    
    async def _build_artist_from_musicbrainz(
        self,
        artist_id: str,
        library_artist_mbids: set[str] = None,
        library_album_mbids: dict[str, Any] = None,
        include_extended: bool = True
    ) -> ArtistInfo:
        mb_artist, library_mbids, album_mbids, requested_mbids = await self._fetch_artist_data(
            artist_id, library_artist_mbids, library_album_mbids
        )
        in_library = artist_id.lower() in library_mbids
        albums, singles, eps = await self._get_categorized_releases(mb_artist, album_mbids, requested_mbids)
        description, image = (await self._fetch_wikidata_info(mb_artist)) if include_extended else (None, None)
        info = build_base_artist_info(
            mb_artist, artist_id, in_library,
            extract_tags(mb_artist), extract_aliases(mb_artist), extract_life_span(mb_artist),
            self._build_external_links(mb_artist), albums, singles, eps, description, image
        )
        return ArtistInfo(**info)

    async def get_artist_info_basic(self, artist_id: str) -> ArtistInfo:
        artist_id = validate_mbid(artist_id, "artist")
        cached = await self._get_cached_artist(artist_id)
        if cached:
            return cached
        logger.debug(f"Cache MISS (Disk): Artist {artist_id[:8]}... - fetching from API")
        artist_info = await self._build_artist_from_musicbrainz(artist_id, include_extended=False)
        await self._save_artist_to_cache(artist_id, artist_info)
        return artist_info

    async def _get_cached_artist(self, artist_id: str) -> Optional[ArtistInfo]:
        cache_key = f"artist_info:{artist_id}"
        cached_info = await self._cache.get(cache_key)
        if cached_info:
            logger.debug(f"Cache HIT (RAM): Artist {artist_id[:8]}...")
            return cached_info
        logger.debug(f"Cache MISS (RAM): Artist {artist_id[:8]}...")
        disk_data = await self._disk_cache.get_artist(artist_id)
        if disk_data:
            logger.debug(f"Cache HIT (Disk): Artist {artist_id[:8]}...")
            artist_info = ArtistInfo(**disk_data)
            ttl = self._get_artist_ttl(artist_info.in_library)
            await self._cache.set(cache_key, artist_info, ttl_seconds=ttl)
            return artist_info
        return None

    async def _save_artist_to_cache(self, artist_id: str, artist_info: ArtistInfo) -> None:
        cache_key = f"artist_info:{artist_id}"
        ttl = self._get_artist_ttl(artist_info.in_library)
        await self._cache.set(cache_key, artist_info, ttl_seconds=ttl)
        await self._disk_cache.set_artist(
            artist_id, artist_info,
            is_monitored=artist_info.in_library,
            ttl_seconds=ttl if not artist_info.in_library else None
        )

    def _get_artist_ttl(self, in_library: bool) -> int:
        advanced_settings = self._preferences_service.get_advanced_settings()
        return advanced_settings.cache_ttl_artist_library if in_library else advanced_settings.cache_ttl_artist_non_library
    
    async def get_artist_extended_info(self, artist_id: str) -> ArtistExtendedInfo:
        try:
            artist_id = validate_mbid(artist_id, "artist")
            cache_key = f"artist_info:{artist_id}"
            cached_info = await self._cache.get(cache_key)
            if cached_info and cached_info.description is not None:
                logger.debug(f"Extended info cache HIT: Artist {artist_id[:8]}...")
                return ArtistExtendedInfo(description=cached_info.description, image=cached_info.image)
            mb_artist = await self._mb_repo.get_artist_by_id(artist_id)
            if not mb_artist:
                raise ResourceNotFoundError("Artist not found")
            description, image = await self._fetch_wikidata_info(mb_artist)
            if cached_info:
                cached_info.description = description
                cached_info.image = image
                await self._save_artist_to_cache(artist_id, cached_info)
            return ArtistExtendedInfo(description=description, image=image)
        except Exception as e:
            logger.error(f"Error fetching extended artist info for {artist_id}: {e}")
            return ArtistExtendedInfo(description=None, image=None)
    
    async def get_artist_releases(
        self,
        artist_id: str,
        offset: int = 0,
        limit: int = 50
    ) -> ArtistReleases:
        try:
            lidarr_artist = await self._lidarr_repo.get_artist_details(artist_id)
            in_library = lidarr_artist is not None and lidarr_artist.get("monitored", False)

            album_mbids, requested_mbids = await asyncio.gather(
                self._lidarr_repo.get_library_mbids(include_release_ids=True),
                self._lidarr_repo.get_requested_mbids(),
            )

            prefs = self._preferences_service.get_preferences()
            included_primary_types = set(t.lower() for t in prefs.primary_types)
            included_secondary_types = set(t.lower() for t in prefs.secondary_types)

            if in_library and offset == 0:
                logger.debug(f"Using Lidarr for artist releases {artist_id[:8]}")
                lidarr_albums = await self._lidarr_repo.get_artist_albums(artist_id)
                albums, singles, eps = self._categorize_lidarr_albums(lidarr_albums, album_mbids)

                total_count = len(albums) + len(singles) + len(eps)

                return ArtistReleases(
                    albums=albums,
                    singles=singles,
                    eps=eps,
                    total_count=total_count,
                    has_more=False
                )

            logger.debug(f"Using MusicBrainz for artist releases {artist_id[:8]}")
            release_groups, total_count = await self._mb_repo.get_artist_release_groups(
                artist_id, offset, limit
            )

            temp_artist = {"release-group-list": release_groups}

            albums, singles, eps = categorize_release_groups(
                temp_artist,
                album_mbids,
                included_primary_types,
                included_secondary_types,
                requested_mbids
            )
            
            has_more = (offset + len(release_groups)) < total_count
            
            return ArtistReleases(
                albums=albums,
                singles=singles,
                eps=eps,
                total_count=total_count,
                has_more=has_more
            )
        except Exception as e:
            logger.error(f"Error fetching releases for artist {artist_id} at offset {offset}: {e}")
            return ArtistReleases(albums=[], singles=[], eps=[], total_count=0, has_more=False)
    
    async def _fetch_artist_data(
        self,
        artist_id: str,
        library_artist_mbids: set[str] = None,
        library_album_mbids: dict[str, Any] = None
    ) -> tuple[dict, set[str], set[str], set[str]]:
        try:
            if library_artist_mbids is not None and library_album_mbids is not None:
                mb_artist, requested_mbids = await asyncio.gather(
                    self._mb_repo.get_artist_by_id(artist_id),
                    self._lidarr_repo.get_requested_mbids(),
                )
                library_mbids = library_artist_mbids
                album_mbids = library_album_mbids
            else:
                mb_artist, library_mbids, album_mbids, requested_mbids = await asyncio.gather(
                    self._mb_repo.get_artist_by_id(artist_id),
                    self._lidarr_repo.get_artist_mbids(),
                    self._lidarr_repo.get_library_mbids(include_release_ids=True),
                    self._lidarr_repo.get_requested_mbids(),
                )
        except Exception as e:
            logger.error(f"Error fetching artist data for {artist_id}: {e}")
            raise ResourceNotFoundError(f"Failed to fetch artist: {e}")

        if not mb_artist:
            raise ResourceNotFoundError("Artist not found")

        return mb_artist, library_mbids, album_mbids, requested_mbids
    
    def _build_external_links(self, mb_artist: dict[str, Any]) -> list[ExternalLink]:
        external_links_data = extract_external_links(mb_artist)
        return [
            ExternalLink(type=link["type"], url=link["url"], label=link["label"])
            for link in external_links_data
        ]

    async def _get_categorized_releases(
        self,
        mb_artist: dict[str, Any],
        album_mbids: set[str],
        requested_mbids: set[str] = None
    ) -> tuple[list[dict], list[dict], list[dict]]:
        prefs = self._preferences_service.get_preferences()
        included_primary_types = set(t.lower() for t in prefs.primary_types)
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        return categorize_release_groups(
            mb_artist,
            album_mbids,
            included_primary_types,
            included_secondary_types,
            requested_mbids or set()
        )
    
    async def _fetch_wikidata_info(self, mb_artist: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        wikidata_id, wiki_urls = self._extract_wiki_info(mb_artist)
        
        tasks = []
        if wiki_urls:
            tasks.append(self._wikidata_repo.get_wikipedia_extract(wiki_urls[0]))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))
        
        if wikidata_id:
            tasks.append(self._wikidata_repo.get_artist_image_from_wikidata(wikidata_id))
        else:
            tasks.append(asyncio.create_task(asyncio.sleep(0)))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        description = results[0] if len(results) > 0 and not isinstance(results[0], Exception) and results[0] else None
        image = results[1] if len(results) > 1 and not isinstance(results[1], Exception) and results[1] else None
        
        return description, image
    
    def _extract_wiki_info(self, mb_artist: dict[str, Any]) -> tuple[Optional[str], list[str]]:
        return extract_wiki_info(mb_artist, self._wikidata_repo.get_wikidata_id_from_url)
