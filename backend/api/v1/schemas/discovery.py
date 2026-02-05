from typing import Optional
from pydantic import BaseModel, Field


class SimilarArtist(BaseModel):
    musicbrainz_id: str
    name: str
    listen_count: int = 0
    in_library: bool = False
    image_url: Optional[str] = None


class SimilarArtistsResponse(BaseModel):
    similar_artists: list[SimilarArtist] = Field(default_factory=list)
    source: str = "listenbrainz"
    configured: bool = True


class TopSong(BaseModel):
    recording_mbid: Optional[str] = None
    title: str
    artist_name: str
    release_mbid: Optional[str] = None
    release_name: Optional[str] = None
    listen_count: int = 0


class TopSongsResponse(BaseModel):
    songs: list[TopSong] = Field(default_factory=list)
    source: str = "listenbrainz"
    configured: bool = True


class TopAlbum(BaseModel):
    release_group_mbid: Optional[str] = None
    title: str
    artist_name: str
    year: Optional[int] = None
    listen_count: int = 0
    in_library: bool = False
    requested: bool = False
    cover_url: Optional[str] = None


class TopAlbumsResponse(BaseModel):
    albums: list[TopAlbum] = Field(default_factory=list)
    source: str = "listenbrainz"
    configured: bool = True


class DiscoveryAlbum(BaseModel):
    musicbrainz_id: str
    title: str
    artist_name: str
    artist_id: Optional[str] = None
    year: Optional[int] = None
    in_library: bool = False
    requested: bool = False
    cover_url: Optional[str] = None


class SimilarAlbumsResponse(BaseModel):
    albums: list[DiscoveryAlbum] = Field(default_factory=list)
    source: str = "listenbrainz"
    configured: bool = True


class MoreByArtistResponse(BaseModel):
    albums: list[DiscoveryAlbum] = Field(default_factory=list)
    artist_name: str = ""
