import msgspec
from infrastructure.msgspec_fastapi import AppStruct


class ProfileSettings(AppStruct):
    display_name: str = ""
    avatar_url: str = ""


class ServiceConnection(AppStruct):
    name: str
    enabled: bool = False
    username: str = ""
    url: str = ""


class LibraryStats(AppStruct):
    source: str
    total_tracks: int = 0
    total_albums: int = 0
    total_artists: int = 0
    total_size_bytes: int = 0
    total_size_human: str = ""


class ProfileResponse(AppStruct):
    display_name: str = ""
    avatar_url: str = ""
    services: list[ServiceConnection] = msgspec.field(default_factory=list)
    library_stats: list[LibraryStats] = msgspec.field(default_factory=list)


class ProfileUpdateRequest(AppStruct):
    display_name: str | None = None
    avatar_url: str | None = None
