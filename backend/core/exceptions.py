from typing import Any


class MusicseerrException(Exception):
    def __init__(self, message: str, details: Any = None):
        self.message = message
        self.details = details
        super().__init__(message)
    
    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class ExternalServiceError(MusicseerrException):
    pass


class RateLimitedError(ExternalServiceError):
    def __init__(
        self,
        message: str,
        details: Any = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(message, details)
        self.retry_after_seconds = retry_after_seconds


class ResourceNotFoundError(MusicseerrException):
    pass


class ValidationError(MusicseerrException):
    pass


class PlaylistNotFoundError(ResourceNotFoundError):
    pass


class InvalidPlaylistDataError(ValidationError):
    pass


class SourceResolutionError(ValidationError):
    pass


class ConfigurationError(MusicseerrException):
    pass


class CacheError(MusicseerrException):
    pass


class PlaybackNotAllowedError(ExternalServiceError):
    pass


class TokenNotAuthorizedError(ExternalServiceError):
    pass
