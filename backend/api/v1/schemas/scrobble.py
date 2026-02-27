import time

from pydantic import BaseModel, Field, field_validator


class NowPlayingRequest(BaseModel):
    track_name: str = Field(description="Track name")
    artist_name: str = Field(description="Artist name")
    album_name: str = Field(default="", description="Album name")
    duration_ms: int = Field(default=0, ge=0, description="Track duration in milliseconds")
    mbid: str | None = Field(default=None, description="MusicBrainz recording ID")


class ScrobbleRequest(BaseModel):
    track_name: str = Field(description="Track name")
    artist_name: str = Field(description="Artist name")
    album_name: str = Field(default="", description="Album name")
    timestamp: int = Field(description="Unix epoch timestamp when the track was played")
    duration_ms: int = Field(default=0, ge=0, description="Track duration in milliseconds")
    mbid: str | None = Field(default=None, description="MusicBrainz recording ID")

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: int) -> int:
        now = int(time.time())
        max_age = 14 * 24 * 60 * 60
        if v > now + 60:
            raise ValueError("Timestamp cannot be in the future")
        if v < now - max_age:
            raise ValueError("Timestamp cannot be older than 14 days")
        return v


class ServiceResult(BaseModel):
    success: bool = Field(description="Whether the scrobble was accepted by this service")
    error: str | None = Field(default=None, description="Error message if submission failed")


class ScrobbleResponse(BaseModel):
    accepted: bool = Field(description="Whether at least one service accepted the scrobble")
    services: dict[str, ServiceResult] = Field(
        default_factory=dict,
        description="Per-service submission results",
    )
