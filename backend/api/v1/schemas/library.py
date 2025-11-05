from typing import Optional
from pydantic import BaseModel, Field


class LibraryAlbum(BaseModel):
    artist: str
    album: str
    year: Optional[int] = None
    monitored: bool
    quality: Optional[str] = None
    cover_url: Optional[str] = None
    musicbrainz_id: Optional[str] = Field(None, alias="foreignAlbumId")

    class Config:
        populate_by_name = True


class LibraryResponse(BaseModel):
    library: list[LibraryAlbum]
