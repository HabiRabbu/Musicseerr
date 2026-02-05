import asyncio
import logging
from api.v1.schemas.discovery import (
    DiscoveryAlbum,
    SimilarAlbumsResponse,
    MoreByArtistResponse,
)
from repositories.listenbrainz_repository import ListenBrainzRepository
from repositories.protocols import MusicBrainzRepositoryProtocol
from repositories.lidarr import LidarrRepository
from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


class AlbumDiscoveryService:
    def __init__(
        self,
        listenbrainz_repo: ListenBrainzRepository,
        musicbrainz_repo: MusicBrainzRepositoryProtocol,
        library_cache: LibraryCache,
        lidarr_repo: LidarrRepository,
    ):
        self._lb_repo = listenbrainz_repo
        self._mb_repo = musicbrainz_repo
        self._library_cache = library_cache
        self._lidarr_repo = lidarr_repo

    async def get_similar_albums(
        self,
        album_mbid: str,
        artist_mbid: str,
        count: int = 10
    ) -> SimilarAlbumsResponse:
        if not self._lb_repo.is_configured():
            return SimilarAlbumsResponse(configured=False)

        try:
            similar_artists = await self._lb_repo.get_similar_artists(artist_mbid, max_similar=5)
            if not similar_artists:
                return SimilarAlbumsResponse(albums=[])

            library_album_mbids, requested_album_mbids = await asyncio.gather(
                self._lidarr_repo.get_library_mbids(),
                self._lidarr_repo.get_requested_mbids()
            )

            tasks = [
                self._lb_repo.get_artist_top_release_groups(a.artist_mbid, count=3)
                for a in similar_artists[:5]
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            albums: list[DiscoveryAlbum] = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    continue
                artist = similar_artists[i]
                for rg in result:
                    if rg.release_group_mbid and rg.release_group_mbid != album_mbid:
                        mbid_lower = rg.release_group_mbid.lower()
                        albums.append(DiscoveryAlbum(
                            musicbrainz_id=rg.release_group_mbid,
                            title=rg.release_group_name,
                            artist_name=artist.artist_name,
                            artist_id=artist.artist_mbid,
                            in_library=mbid_lower in library_album_mbids,
                            requested=mbid_lower in requested_album_mbids,
                        ))
                        if len(albums) >= count:
                            break
                if len(albums) >= count:
                    break

            return SimilarAlbumsResponse(albums=albums[:count])
        except Exception as e:
            logger.warning(f"Failed to get similar albums for {album_mbid}: {e}")
            return SimilarAlbumsResponse(albums=[])

    async def get_more_by_artist(
        self,
        artist_mbid: str,
        exclude_album_mbid: str,
        count: int = 10
    ) -> MoreByArtistResponse:
        try:
            release_groups = await self._mb_repo.get_release_groups_by_artist(
                artist_mbid,
                limit=count + 5
            )
            if not release_groups:
                return MoreByArtistResponse(albums=[], artist_name="")

            library_album_mbids, requested_album_mbids = await asyncio.gather(
                self._lidarr_repo.get_library_mbids(),
                self._lidarr_repo.get_requested_mbids()
            )

            albums: list[DiscoveryAlbum] = []
            artist_name = ""

            for rg in release_groups:
                rg_mbid = rg.get("id", "")
                if rg_mbid == exclude_album_mbid:
                    continue

                if not artist_name:
                    artist_credit = rg.get("artist-credit", [])
                    if artist_credit:
                        artist_name = artist_credit[0].get("artist", {}).get("name", "")

                year = None
                first_release = rg.get("first-release-date", "")
                if first_release and len(first_release) >= 4:
                    try:
                        year = int(first_release[:4])
                    except ValueError:
                        pass

                mbid_lower = rg_mbid.lower()
                albums.append(DiscoveryAlbum(
                    musicbrainz_id=rg_mbid,
                    title=rg.get("title", "Unknown"),
                    artist_name=artist_name,
                    artist_id=artist_mbid,
                    year=year,
                    in_library=mbid_lower in library_album_mbids,
                    requested=mbid_lower in requested_album_mbids,
                ))

                if len(albums) >= count:
                    break

            return MoreByArtistResponse(albums=albums, artist_name=artist_name)
        except Exception as e:
            logger.warning(f"Failed to get more albums by artist {artist_mbid}: {e}")
            return MoreByArtistResponse(albums=[], artist_name="")
