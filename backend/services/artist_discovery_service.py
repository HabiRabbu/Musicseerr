import asyncio
import logging
from api.v1.schemas.discovery import (
    SimilarArtist,
    SimilarArtistsResponse,
    TopSong,
    TopSongsResponse,
    TopAlbum,
    TopAlbumsResponse,
)
from repositories.listenbrainz_repository import ListenBrainzRepository
from repositories.protocols import MusicBrainzRepositoryProtocol
from repositories.lidarr import LidarrRepository
from infrastructure.cache.persistent_cache import LibraryCache

logger = logging.getLogger(__name__)


class ArtistDiscoveryService:
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

    async def get_similar_artists(
        self,
        artist_mbid: str,
        count: int = 15
    ) -> SimilarArtistsResponse:
        if not self._lb_repo.is_configured():
            return SimilarArtistsResponse(configured=False)

        try:
            similar = await self._lb_repo.get_similar_artists(artist_mbid, max_similar=count)
            library_artist_mbids = await self._library_cache.get_all_artist_mbids()

            artists = [
                SimilarArtist(
                    musicbrainz_id=a.artist_mbid,
                    name=a.artist_name,
                    listen_count=a.listen_count,
                    in_library=a.artist_mbid in library_artist_mbids,
                )
                for a in similar[:count]
            ]
            return SimilarArtistsResponse(similar_artists=artists)
        except Exception as e:
            logger.warning(f"Failed to get similar artists for {artist_mbid}: {e}")
            return SimilarArtistsResponse(similar_artists=[])

    async def get_top_songs(
        self,
        artist_mbid: str,
        count: int = 10
    ) -> TopSongsResponse:
        if not self._lb_repo.is_configured():
            return TopSongsResponse(configured=False)

        try:
            recordings = await self._lb_repo.get_artist_top_recordings(artist_mbid, count=count)
            
            release_ids = [r.release_mbid for r in recordings if r.release_mbid]
            logger.info(f"Top songs for {artist_mbid}: {len(recordings)} recordings, {len(release_ids)} with release_mbid")
            
            rg_map = await self._resolve_release_groups(release_ids)
            logger.info(f"Resolved {len(rg_map)} release groups from {len(release_ids)} releases")
            
            songs = [
                TopSong(
                    recording_mbid=r.recording_mbid,
                    title=r.track_name,
                    artist_name=r.artist_name,
                    release_mbid=rg_map.get(r.release_mbid) if r.release_mbid else None,
                    release_name=r.release_name,
                    listen_count=r.listen_count,
                )
                for r in recordings[:count]
            ]
            return TopSongsResponse(songs=songs)
        except Exception as e:
            logger.warning(f"Failed to get top songs for {artist_mbid}: {e}")
            return TopSongsResponse(songs=[])

    async def get_top_albums(
        self,
        artist_mbid: str,
        count: int = 10
    ) -> TopAlbumsResponse:
        if not self._lb_repo.is_configured():
            return TopAlbumsResponse(configured=False)

        try:
            release_groups = await self._lb_repo.get_artist_top_release_groups(artist_mbid, count=count)
            if not release_groups:
                return TopAlbumsResponse(albums=[])

            library_album_mbids, requested_album_mbids = await asyncio.gather(
                self._lidarr_repo.get_library_mbids(),
                self._lidarr_repo.get_requested_mbids()
            )

            albums = [
                TopAlbum(
                    release_group_mbid=rg.release_group_mbid,
                    title=rg.release_group_name,
                    artist_name=rg.artist_name,
                    listen_count=rg.listen_count,
                    in_library=rg.release_group_mbid.lower() in library_album_mbids if rg.release_group_mbid else False,
                    requested=rg.release_group_mbid.lower() in requested_album_mbids if rg.release_group_mbid else False,
                )
                for rg in release_groups
            ]
            return TopAlbumsResponse(albums=albums)
        except Exception as e:
            logger.warning(f"Failed to get top albums for {artist_mbid}: {e}")
            return TopAlbumsResponse(albums=[])

    async def _resolve_release_groups(self, release_ids: list[str]) -> dict[str, str]:
        if not release_ids:
            return {}
        
        logger.info(f"Resolving {len(release_ids)} release IDs to release groups")
        tasks = [self._mb_repo.get_release_group_id_from_release(rid) for rid in release_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        rg_map = {}
        errors = 0
        for rid, rg_id in zip(release_ids, results):
            if isinstance(rg_id, Exception):
                errors += 1
                logger.warning(f"Resolution exception for {rid}: {rg_id}")
            elif isinstance(rg_id, str) and rg_id:
                rg_map[rid] = rg_id
            else:
                errors += 1
                logger.warning(f"Resolution returned None/empty for {rid}")
        
        logger.info(f"Release group resolution: {len(rg_map)} succeeded, {errors} failed")
        return rg_map
