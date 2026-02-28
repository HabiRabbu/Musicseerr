from typing import Literal

from infrastructure.msgspec_fastapi import AppStruct


GenreArtistMap = dict[str, str | None]


class IntegrationStatus(AppStruct):
    listenbrainz: bool
    jellyfin: bool
    lidarr: bool
    youtube: bool
    lastfm: bool


class ServiceStatus(AppStruct):
    status: Literal["ok", "error"]
    version: str | None = None
    message: str | None = None


class StatusReport(AppStruct):
    status: Literal["ok", "degraded", "error"]
    services: dict[str, ServiceStatus]


class LastFmTagSchema(AppStruct):
    name: str
    url: str | None = None


class StatusMessageResponse(AppStruct):
    status: str
    message: str


class VerifyConnectionResponse(AppStruct):
    valid: bool
    message: str
