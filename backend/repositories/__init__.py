"""Repository layer with Protocol interfaces for dependency inversion."""

from repositories.protocols import (
    MusicBrainzRepositoryProtocol,
    LidarrRepositoryProtocol,
    WikidataRepositoryProtocol,
    CoverArtRepositoryProtocol,
)

__all__ = [
    "MusicBrainzRepositoryProtocol",
    "LidarrRepositoryProtocol",
    "WikidataRepositoryProtocol",
    "CoverArtRepositoryProtocol",
]
