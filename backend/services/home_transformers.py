from api.v1.schemas.home import HomeArtist, HomeAlbum, HomeGenre
from api.v1.schemas.library import LibraryAlbum
from repositories.protocols import (
    ListenBrainzArtist,
    ListenBrainzReleaseGroup,
    JellyfinItem,
    JellyfinRepositoryProtocol,
)


class HomeDataTransformers:
    def __init__(self, jellyfin_repo: JellyfinRepositoryProtocol | None = None):
        self._jf_repo = jellyfin_repo

    def lidarr_album_to_home(self, album: LibraryAlbum) -> HomeAlbum:
        return HomeAlbum(
            mbid=album.musicbrainz_id,
            name=album.album or "Unknown Album",
            artist_name=album.artist,
            artist_mbid=album.artist_mbid,
            image_url=album.cover_url,
            release_date=str(album.year) if album.year else None,
            in_library=True,
        )

    def lidarr_artist_to_home(self, artist_data: dict) -> HomeArtist | None:
        mbid = artist_data.get("mbid")
        if not mbid:
            return None
        return HomeArtist(
            mbid=mbid,
            name=artist_data.get("name", "Unknown Artist"),
            image_url=None,
            listen_count=artist_data.get("album_count"),
            in_library=True,
        )

    def lb_artist_to_home(
        self,
        artist: ListenBrainzArtist,
        library_mbids: set[str]
    ) -> HomeArtist | None:
        mbid = artist.artist_mbids[0] if artist.artist_mbids else None
        if not mbid:
            return None
        return HomeArtist(
            mbid=mbid,
            name=artist.artist_name,
            image_url=None,
            listen_count=artist.listen_count,
            in_library=mbid.lower() in library_mbids,
        )

    def lb_release_to_home(
        self,
        release: ListenBrainzReleaseGroup,
        library_mbids: set[str]
    ) -> HomeAlbum:
        artist_mbid = release.artist_mbids[0] if release.artist_mbids else None
        return HomeAlbum(
            mbid=release.release_group_mbid,
            name=release.release_group_name,
            artist_name=release.artist_name,
            artist_mbid=artist_mbid,
            image_url=None,
            release_date=None,
            listen_count=release.listen_count,
            in_library=(release.release_group_mbid or "").lower() in library_mbids,
        )

    def jf_item_to_artist(
        self,
        item: JellyfinItem,
        library_mbids: set[str]
    ) -> HomeArtist | None:
        mbid = None
        if item.provider_ids:
            mbid = item.provider_ids.get("MusicBrainzArtist")

        artist_name = item.artist_name or item.name
        if not artist_name:
            return None

        image_url = None
        if self._jf_repo:
            if item.artist_id:
                image_url = self._jf_repo.get_image_url(item.artist_id, item.image_tag)
            else:
                image_url = self._jf_repo.get_image_url(item.id, item.image_tag)

        return HomeArtist(
            mbid=mbid,
            name=artist_name,
            image_url=image_url,
            listen_count=item.play_count,
            in_library=mbid.lower() in library_mbids if mbid else False,
        )

    def extract_genres_from_library(
        self,
        albums: list[LibraryAlbum],
        lb_genres: list | None = None
    ) -> list[HomeGenre]:
        if lb_genres:
            return [
                HomeGenre(name=g.genre, listen_count=g.listen_count)
                for g in lb_genres[:20]
            ]

        default_genres = [
            "Rock", "Pop", "Hip Hop", "Electronic", "Jazz",
            "Classical", "R&B", "Country", "Metal", "Folk",
            "Blues", "Reggae", "Soul", "Punk", "Indie",
            "Alternative", "Dance", "Soundtrack", "World", "Latin"
        ]

        return [HomeGenre(name=g) for g in default_genres]

    @staticmethod
    def get_range_label(range_key: str) -> str:
        labels = {
            "this_week": "This Week",
            "this_month": "This Month",
            "this_year": "This Year",
            "all_time": "All Time",
            "week": "This Week",
            "month": "This Month",
            "year": "This Year",
        }
        return labels.get(range_key, range_key.replace("_", " ").title())
