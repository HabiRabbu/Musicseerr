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


class ResourceNotFoundError(MusicseerrException):
    pass


class ValidationError(MusicseerrException):
    pass


class ConfigurationError(MusicseerrException):
    pass


class CacheError(MusicseerrException):
    pass


class PlaybackNotAllowedError(ExternalServiceError):
    pass
