from typing import Optional
from pydantic import BaseModel, Field, field_validator
from infrastructure.validators import sanitize_optional_string


class LibraryAlbum(BaseModel):
    artist: str
    album: str
    year: Optional[int] = None
    monitored: bool
    quality: Optional[str] = None
    cover_url: Optional[str] = None
    musicbrainz_id: Optional[str] = Field(None, alias="foreignAlbumId")
    artist_mbid: Optional[str] = None
    date_added: Optional[int] = None

    @field_validator('cover_url', 'quality', 'musicbrainz_id', 'artist_mbid', mode='before')
    @classmethod
    def sanitize_strings(cls, v):
        return sanitize_optional_string(v)

    class Config:
        populate_by_name = True


class LibraryArtist(BaseModel):
    mbid: str = Field(..., description="MusicBrainz artist ID")
    name: str = Field(..., description="Artist name")
    album_count: int = Field(0, description="Number of albums by this artist")
    date_added: Optional[int] = Field(None, description="Unix timestamp when added")


class LibraryResponse(BaseModel):
    library: list[LibraryAlbum]


class LibraryArtistsResponse(BaseModel):
    artists: list[LibraryArtist]
    total: int = Field(..., description="Total number of artists")


class LibraryAlbumsResponse(BaseModel):
    albums: list[LibraryAlbum]
    total: int = Field(..., description="Total number of albums")


class RecentlyAddedResponse(BaseModel):
    albums: list[LibraryAlbum] = Field(default_factory=list)
    artists: list[LibraryArtist] = Field(default_factory=list)


class LibraryStatsResponse(BaseModel):
    artist_count: int
    album_count: int
    last_sync: Optional[int] = Field(None, description="Unix timestamp of last sync")
    db_size_bytes: int
    db_size_mb: float


class AlbumRemoveResponse(BaseModel):
    success: bool
    artist_removed: bool = False
    artist_name: Optional[str] = None


class AlbumRemovePreviewResponse(BaseModel):
    success: bool
    artist_will_be_removed: bool = False
    artist_name: Optional[str] = None
