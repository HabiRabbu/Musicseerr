import asyncio
import logging
from typing import Any, Optional
from api.v1.schemas.artist import ArtistInfo, ArtistExtendedInfo, ArtistReleases, ExternalLink
from repositories.musicbrainz_repository import MusicBrainzRepository
from repositories.lidarr_repository import LidarrRepository
from repositories.wikidata_repository import WikidataRepository
from services.preferences_service import PreferencesService
from core.exceptions import ResourceNotFoundError

logger = logging.getLogger(__name__)

_PLATFORM_PATTERNS = {
    "instagram.com": "Instagram",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "facebook.com": "Facebook",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
    "spotify.com": "Spotify",
    "deezer.com": "Deezer",
    "apple.com": "Apple Music",
    "music.apple.com": "Apple Music",
    "tidal.com": "Tidal",
    "amazon.": "Amazon",
    "bandcamp.com": "Bandcamp",
}

_LINK_TYPE_LABELS = {
    "official homepage": "Official Website",
    "wikipedia": "Wikipedia",
    "wikidata": "Wikidata",
    "discogs": "Discogs",
    "allmusic": "AllMusic",
    "bandcamp": "Bandcamp",
    "last.fm": "Last.fm",
    "youtube": "YouTube",
    "soundcloud": "SoundCloud",
    "instagram": "Instagram",
    "twitter": "Twitter",
    "facebook": "Facebook",
}


class ArtistService:
    def __init__(
        self,
        mb_repo: MusicBrainzRepository,
        lidarr_repo: LidarrRepository,
        wikidata_repo: WikidataRepository,
        preferences_service: PreferencesService
    ):
        self._mb_repo = mb_repo
        self._lidarr_repo = lidarr_repo
        self._wikidata_repo = wikidata_repo
        self._preferences_service = preferences_service
    
    async def get_artist_info(self, artist_id: str) -> ArtistInfo:
        """Get comprehensive artist information.
        
        Main orchestration method - delegates to smaller helper methods.
        """
        mb_artist, library_mbids, album_mbids = await self._fetch_artist_data(artist_id)
        
        in_library = artist_id.lower() in library_mbids
        tags = self._extract_tags(mb_artist)
        aliases = self._extract_aliases(mb_artist)
        life_span = self._extract_life_span(mb_artist)
        external_links = self._build_external_links(mb_artist)
        
        albums, singles, eps = await self._get_categorized_releases(mb_artist, album_mbids)
        
        description, image = await self._fetch_wikidata_info(mb_artist)
        
        return ArtistInfo(
            name=mb_artist.get("name", "Unknown Artist"),
            musicbrainz_id=artist_id,
            disambiguation=mb_artist.get("disambiguation"),
            type=mb_artist.get("type"),
            country=mb_artist.get("country"),
            life_span=life_span,
            description=description,
            image=image,
            tags=tags,
            aliases=aliases,
            external_links=external_links,
            in_library=in_library,
            albums=albums,
            singles=singles,
            eps=eps,
        )
    
    async def get_artist_info_basic(self, artist_id: str) -> ArtistInfo:
        mb_artist, library_mbids, album_mbids = await self._fetch_artist_data(artist_id)
        
        in_library = artist_id.lower() in library_mbids
        tags = self._extract_tags(mb_artist)
        aliases = self._extract_aliases(mb_artist)
        life_span = self._extract_life_span(mb_artist)
        external_links = self._build_external_links(mb_artist)
        
        albums, singles, eps = await self._get_categorized_releases(mb_artist, album_mbids)
        
        total_release_count = mb_artist.get("release-group-count", 0)
        
        return ArtistInfo(
            name=mb_artist.get("name", "Unknown Artist"),
            musicbrainz_id=artist_id,
            disambiguation=mb_artist.get("disambiguation"),
            type=mb_artist.get("type"),
            country=mb_artist.get("country"),
            life_span=life_span,
            description=None,
            image=None,
            tags=tags,
            aliases=aliases,
            external_links=external_links,
            in_library=in_library,
            albums=albums,
            singles=singles,
            eps=eps,
            release_group_count=total_release_count,
        )
    
    async def get_artist_extended_info(self, artist_id: str) -> ArtistExtendedInfo:
        try:
            mb_artist = await self._mb_repo.get_artist_by_id(artist_id)
            if not mb_artist:
                raise ResourceNotFoundError("Artist not found")
            
            description, image = await self._fetch_wikidata_info(mb_artist)
            
            return ArtistExtendedInfo(
                description=description,
                image=image
            )
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
            release_groups, total_count = await self._mb_repo.get_artist_release_groups(
                artist_id, offset, limit
            )
            
            album_mbids = await self._lidarr_repo.get_library_mbids(include_release_ids=True)
            
            temp_artist = {"release-group-list": release_groups}
            
            prefs = self._preferences_service.get_preferences()
            included_primary_types = set(t.lower() for t in prefs.primary_types)
            included_secondary_types = set(t.lower() for t in prefs.secondary_types)
            
            albums, singles, eps = self._categorize_release_groups(
                temp_artist,
                album_mbids,
                included_primary_types,
                included_secondary_types
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
    
    async def _fetch_artist_data(self, artist_id: str) -> tuple[dict, set[str], set[str]]:
        """Fetch artist data from MusicBrainz and library info from Lidarr."""
        try:
            mb_artist, library_mbids, album_mbids = await asyncio.gather(
                self._mb_repo.get_artist_by_id(artist_id),
                self._lidarr_repo.get_artist_mbids(),
                self._lidarr_repo.get_library_mbids(include_release_ids=True),
            )
        except Exception as e:
            logger.error(f"Error fetching artist data for {artist_id}: {e}")
            raise ResourceNotFoundError(f"Failed to fetch artist: {e}")
        
        if not mb_artist:
            raise ResourceNotFoundError("Artist not found")
        
        return mb_artist, library_mbids, album_mbids
    
    def _build_external_links(self, mb_artist: dict[str, Any]) -> list[ExternalLink]:
        """Build external links list from artist data."""
        external_links_data = self._extract_external_links(mb_artist)
        return [
            ExternalLink(type=link["type"], url=link["url"], label=link["label"])
            for link in external_links_data
        ]
    
    async def _get_categorized_releases(
        self,
        mb_artist: dict[str, Any],
        album_mbids: set[str]
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Get and categorize release groups by type."""
        prefs = self._preferences_service.get_preferences()
        included_primary_types = set(t.lower() for t in prefs.primary_types)
        included_secondary_types = set(t.lower() for t in prefs.secondary_types)
        
        return self._categorize_release_groups(
            mb_artist,
            album_mbids,
            included_primary_types,
            included_secondary_types
        )
    
    async def _fetch_wikidata_info(self, mb_artist: dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Fetch Wikipedia description and artist image in parallel."""
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
        """Extract Wikidata ID and Wikipedia URLs from artist data."""
        wikidata_id = None
        wiki_urls = []
        
        if url_rels := mb_artist.get("url-relation-list", []):
            for url_rel in url_rels:
                url_type = url_rel.get("type")
                wiki_url = url_rel.get("target")
                
                if not wiki_url:
                    continue
                
                if url_type == "wikidata" and not wikidata_id:
                    wikidata_id = self._wikidata_repo.get_wikidata_id_from_url(wiki_url)
                
                if url_type in ("wikipedia", "wikidata"):
                    wiki_urls.append(wiki_url)
        
        return wikidata_id, wiki_urls
    
    @staticmethod
    def _extract_tags(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
        """Extract tags from artist data."""
        tags = []
        if mb_tags := mb_artist.get("tag-list", []):
            tags = [tag.get("name") for tag in mb_tags if tag.get("name")][:limit]
        return tags
    
    @staticmethod
    def _extract_aliases(mb_artist: dict[str, Any], limit: int = 10) -> list[str]:
        """Extract aliases from artist data."""
        aliases = []
        if mb_aliases := mb_artist.get("alias-list", []):
            aliases = [
                alias.get("alias") or alias.get("name")
                for alias in mb_aliases
                if alias.get("alias") or alias.get("name")
            ][:limit]
        return aliases
    
    @staticmethod
    def _extract_life_span(mb_artist: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Extract life span information from artist data."""
        if life_span := mb_artist.get("life-span"):
            return {
                "begin": life_span.get("begin"),
                "end": life_span.get("end"),
                "ended": life_span.get("ended")
            }
        return None
    
    @staticmethod
    def _detect_platform(url: str, rel_type: str) -> str:
        """Detect platform from URL and relationship type."""
        url_lower = url.lower()
        
        for pattern, platform in _PLATFORM_PATTERNS.items():
            if pattern in url_lower:
                return platform
        
        if rel_type == "social network":
            return "Social Media"
        elif rel_type == "free streaming":
            return "Streaming"
        elif rel_type == "purchase for download":
            return "Purchase"
        
        return _LINK_TYPE_LABELS.get(rel_type, rel_type.title())
    
    @staticmethod
    def _extract_external_links(mb_artist: dict[str, Any]) -> list[dict[str, str]]:
        """Extract external links from artist data."""
        external_links = []
        seen_urls = set()
        
        if url_rels := mb_artist.get("url-relation-list", []):
            for url_rel in url_rels:
                rel_type = url_rel.get("type", "")
                target_url = url_rel.get("target", "")
                
                if not target_url or target_url in seen_urls:
                    continue
                
                label = ArtistService._detect_platform(target_url, rel_type)
                
                external_links.append({
                    "type": rel_type,
                    "url": target_url,
                    "label": label
                })
                seen_urls.add(target_url)
        
        return external_links
    
    @staticmethod
    def _categorize_release_groups(
        mb_artist: dict[str, Any],
        album_mbids: set[str],
        included_primary_types: Optional[set[str]] = None,
        included_secondary_types: Optional[set[str]] = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Categorize release groups into albums, singles, and EPs."""
        if included_primary_types is None:
            included_primary_types = {"album", "single", "ep", "broadcast", "other"}
        
        albums = []
        singles = []
        eps = []
        
        if rg_list := mb_artist.get("release-group-list", []):
            for rg in rg_list:
                rg_id = rg.get("id")
                primary_type = (rg.get("primary-type") or "").lower()
                
                if primary_type not in included_primary_types:
                    continue
                
                if included_secondary_types is not None:
                    secondary_types = set(map(str.lower, rg.get("secondary-type-list", []) or []))
                    
                    if not secondary_types:
                        if "studio" not in included_secondary_types:
                            continue
                    elif not secondary_types.intersection(included_secondary_types):
                        continue
                
                rg_data = {
                    "id": rg_id,
                    "title": rg.get("title"),
                    "type": rg.get("primary-type"),
                    "first_release_date": rg.get("first-release-date"),
                    "in_library": rg_id.lower() in album_mbids if rg_id else False,
                }
                
                if date := rg_data.get("first_release_date"):
                    try:
                        rg_data["year"] = int(date.split("-")[0])
                    except (ValueError, AttributeError):
                        pass
                
                if primary_type == "album":
                    albums.append(rg_data)
                elif primary_type == "single":
                    singles.append(rg_data)
                elif primary_type == "ep":
                    eps.append(rg_data)
            
            for lst in [albums, singles, eps]:
                lst.sort(key=lambda x: (x.get("year") is None, -(x.get("year") or 0)))
        
        return albums, singles, eps
