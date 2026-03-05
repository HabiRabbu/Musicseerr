import msgspec

from infrastructure.msgspec_fastapi import AppStruct


def _validate_range(value: int | float, field_name: str, minimum: int | float, maximum: int | float) -> None:
    if value < minimum or value > maximum:
        raise msgspec.ValidationError(f"{field_name} must be between {minimum} and {maximum}")


def _coerce_positive_int(value: object, field_name: str) -> int:
    if value is None:
        raise msgspec.ValidationError(f"{field_name} cannot be null")
    try:
        result = int(float(value))
    except (TypeError, ValueError) as exc:
        raise msgspec.ValidationError(f"Invalid integer value for {field_name}: {value}") from exc
    if result <= 0:
        raise msgspec.ValidationError(f"{field_name} must be positive")
    return result


class AdvancedSettings(AppStruct):
    cache_ttl_album_library: int = 86400
    cache_ttl_album_non_library: int = 21600
    cache_ttl_artist_library: int = 21600
    cache_ttl_artist_non_library: int = 21600
    cache_ttl_artist_discovery_library: int = 21600
    cache_ttl_artist_discovery_non_library: int = 3600
    cache_ttl_search: int = 3600
    cache_ttl_local_files_recently_added: int = 120
    cache_ttl_local_files_storage_stats: int = 300
    cache_ttl_jellyfin_recently_played: int = 300
    cache_ttl_jellyfin_favorites: int = 300
    cache_ttl_jellyfin_genres: int = 3600
    cache_ttl_jellyfin_library_stats: int = 600
    http_timeout: int = 10
    http_connect_timeout: int = 5
    http_max_connections: int = 200
    batch_artist_images: int = 5
    batch_albums: int = 3
    delay_artist: float = 0.5
    delay_albums: float = 1.0
    artist_discovery_warm_interval: int = 14400
    artist_discovery_warm_delay: float = 0.5
    artist_discovery_precache_delay: float = 0.3
    memory_cache_max_entries: int = 10000
    memory_cache_cleanup_interval: int = 300
    cover_memory_cache_max_entries: int = 128
    cover_memory_cache_max_size_mb: int = 16
    disk_cache_cleanup_interval: int = 600
    recent_metadata_max_size_mb: int = 500
    recent_covers_max_size_mb: int = 1024
    persistent_metadata_ttl_hours: int = 24
    musicbrainz_concurrent_searches: int = 3
    discover_queue_size: int = 10
    discover_queue_ttl: int = 86400
    discover_queue_auto_generate: bool = True
    discover_queue_polling_interval: int = 4000
    discover_queue_warm_cycle_build: bool = True
    discover_queue_seed_artists: int = 3
    discover_queue_wildcard_slots: int = 2
    discover_queue_similar_artists_limit: int = 15
    discover_queue_albums_per_similar: int = 5
    discover_queue_enrich_ttl: int = 86400
    discover_queue_lastfm_mbid_max_lookups: int = 10
    frontend_ttl_home: int = 300000
    frontend_ttl_discover: int = 1800000
    frontend_ttl_library: int = 300000
    frontend_ttl_recently_added: int = 300000
    frontend_ttl_discover_queue: int = 86400000
    frontend_ttl_search: int = 300000
    frontend_ttl_local_files_sidebar: int = 120000
    frontend_ttl_jellyfin_sidebar: int = 120000
    frontend_ttl_playlist_sources: int = 900000

    def __post_init__(self) -> None:
        ranges: dict[str, tuple[int | float, int | float]] = {
            "cache_ttl_album_library": (3600, 604800),
            "cache_ttl_album_non_library": (60, 86400),
            "cache_ttl_artist_library": (3600, 604800),
            "cache_ttl_artist_non_library": (3600, 604800),
            "cache_ttl_artist_discovery_library": (3600, 604800),
            "cache_ttl_artist_discovery_non_library": (3600, 604800),
            "cache_ttl_search": (60, 86400),
            "cache_ttl_local_files_recently_added": (60, 3600),
            "cache_ttl_local_files_storage_stats": (60, 3600),
            "cache_ttl_jellyfin_recently_played": (60, 3600),
            "cache_ttl_jellyfin_favorites": (60, 3600),
            "cache_ttl_jellyfin_genres": (60, 86400),
            "cache_ttl_jellyfin_library_stats": (60, 3600),
            "http_timeout": (5, 60),
            "http_connect_timeout": (1, 30),
            "http_max_connections": (50, 500),
            "batch_artist_images": (1, 20),
            "batch_albums": (1, 20),
            "delay_artist": (0.0, 5.0),
            "delay_albums": (0.0, 5.0),
            "artist_discovery_warm_interval": (300, 604800),
            "artist_discovery_warm_delay": (0.0, 5.0),
            "artist_discovery_precache_delay": (0.0, 5.0),
            "memory_cache_max_entries": (1000, 100000),
            "memory_cache_cleanup_interval": (60, 3600),
            "cover_memory_cache_max_entries": (16, 2048),
            "cover_memory_cache_max_size_mb": (1, 1024),
            "disk_cache_cleanup_interval": (60, 3600),
            "recent_metadata_max_size_mb": (100, 5000),
            "recent_covers_max_size_mb": (100, 10000),
            "persistent_metadata_ttl_hours": (1, 168),
            "musicbrainz_concurrent_searches": (2, 5),
            "discover_queue_size": (1, 20),
            "discover_queue_ttl": (3600, 604800),
            "discover_queue_polling_interval": (1000, 30000),
            "discover_queue_seed_artists": (1, 10),
            "discover_queue_wildcard_slots": (0, 10),
            "discover_queue_similar_artists_limit": (5, 50),
            "discover_queue_albums_per_similar": (1, 20),
            "discover_queue_enrich_ttl": (3600, 604800),
            "discover_queue_lastfm_mbid_max_lookups": (1, 50),
            "frontend_ttl_home": (60000, 3600000),
            "frontend_ttl_discover": (60000, 86400000),
            "frontend_ttl_library": (60000, 3600000),
            "frontend_ttl_recently_added": (60000, 3600000),
            "frontend_ttl_discover_queue": (3600000, 604800000),
            "frontend_ttl_search": (60000, 3600000),
            "frontend_ttl_local_files_sidebar": (60000, 3600000),
            "frontend_ttl_jellyfin_sidebar": (60000, 3600000),
            "frontend_ttl_playlist_sources": (60000, 3600000),
        }
        for field_name, (minimum, maximum) in ranges.items():
            _validate_range(getattr(self, field_name), field_name, minimum, maximum)


class FrontendCacheTTLs(AppStruct):
    home: int = 300000
    discover: int = 1800000
    library: int = 300000
    recently_added: int = 300000
    discover_queue: int = 86400000
    search: int = 300000
    local_files_sidebar: int = 120000
    jellyfin_sidebar: int = 120000
    playlist_sources: int = 900000
    discover_queue_polling_interval: int = 4000
    discover_queue_auto_generate: bool = True


class AdvancedSettingsFrontend(AppStruct):
    cache_ttl_album_library: int = 24
    cache_ttl_album_non_library: int = 6
    cache_ttl_artist_library: int = 6
    cache_ttl_artist_non_library: int = 6
    cache_ttl_artist_discovery_library: int = 6
    cache_ttl_artist_discovery_non_library: int = 1
    cache_ttl_search: int = 60
    cache_ttl_local_files_recently_added: int = 2
    cache_ttl_local_files_storage_stats: int = 5
    cache_ttl_jellyfin_recently_played: int = 5
    cache_ttl_jellyfin_favorites: int = 5
    cache_ttl_jellyfin_genres: int = 60
    cache_ttl_jellyfin_library_stats: int = 10
    http_timeout: int = 10
    http_connect_timeout: int = 5
    http_max_connections: int = 200
    batch_artist_images: int = 5
    batch_albums: int = 3
    delay_artist: float = 0.5
    delay_albums: float = 1.0
    artist_discovery_warm_interval: int = 240
    artist_discovery_warm_delay: float = 0.5
    artist_discovery_precache_delay: float = 0.3
    memory_cache_max_entries: int = 10000
    memory_cache_cleanup_interval: int = 300
    cover_memory_cache_max_entries: int = 128
    cover_memory_cache_max_size_mb: int = 16
    disk_cache_cleanup_interval: int = 10
    recent_metadata_max_size_mb: int = 500
    recent_covers_max_size_mb: int = 1024
    persistent_metadata_ttl_hours: int = 24
    musicbrainz_concurrent_searches: int = 3
    discover_queue_size: int = 10
    discover_queue_ttl: int = 24
    discover_queue_auto_generate: bool = True
    discover_queue_polling_interval: int = 4
    discover_queue_warm_cycle_build: bool = True
    discover_queue_seed_artists: int = 3
    discover_queue_wildcard_slots: int = 2
    discover_queue_similar_artists_limit: int = 15
    discover_queue_albums_per_similar: int = 5
    discover_queue_enrich_ttl: int = 24
    discover_queue_lastfm_mbid_max_lookups: int = 10
    frontend_ttl_home: int = 5
    frontend_ttl_discover: int = 30
    frontend_ttl_library: int = 5
    frontend_ttl_recently_added: int = 5
    frontend_ttl_discover_queue: int = 1440
    frontend_ttl_search: int = 5
    frontend_ttl_local_files_sidebar: int = 2
    frontend_ttl_jellyfin_sidebar: int = 2
    frontend_ttl_playlist_sources: int = 15

    def __post_init__(self) -> None:
        int_coerce_fields = [
            "cache_ttl_album_library",
            "cache_ttl_album_non_library",
            "cache_ttl_artist_library",
            "cache_ttl_artist_non_library",
            "cache_ttl_artist_discovery_library",
            "cache_ttl_artist_discovery_non_library",
            "cache_ttl_search",
            "cache_ttl_local_files_recently_added",
            "cache_ttl_local_files_storage_stats",
            "cache_ttl_jellyfin_recently_played",
            "cache_ttl_jellyfin_favorites",
            "cache_ttl_jellyfin_genres",
            "cache_ttl_jellyfin_library_stats",
        ]
        for field_name in int_coerce_fields:
            setattr(self, field_name, _coerce_positive_int(getattr(self, field_name), field_name))

        ranges: dict[str, tuple[int | float, int | float]] = {
            "cache_ttl_album_library": (1, 168),
            "cache_ttl_album_non_library": (1, 24),
            "cache_ttl_artist_library": (1, 168),
            "cache_ttl_artist_non_library": (1, 168),
            "cache_ttl_artist_discovery_library": (1, 168),
            "cache_ttl_artist_discovery_non_library": (1, 168),
            "cache_ttl_search": (1, 1440),
            "cache_ttl_local_files_recently_added": (1, 60),
            "cache_ttl_local_files_storage_stats": (1, 60),
            "cache_ttl_jellyfin_recently_played": (1, 60),
            "cache_ttl_jellyfin_favorites": (1, 60),
            "cache_ttl_jellyfin_genres": (1, 1440),
            "cache_ttl_jellyfin_library_stats": (1, 60),
            "http_timeout": (5, 60),
            "http_connect_timeout": (1, 30),
            "http_max_connections": (50, 500),
            "batch_artist_images": (1, 20),
            "batch_albums": (1, 20),
            "delay_artist": (0.0, 5.0),
            "delay_albums": (0.0, 5.0),
            "artist_discovery_warm_interval": (5, 10080),
            "artist_discovery_warm_delay": (0.0, 5.0),
            "artist_discovery_precache_delay": (0.0, 5.0),
            "memory_cache_max_entries": (1000, 100000),
            "memory_cache_cleanup_interval": (60, 3600),
            "cover_memory_cache_max_entries": (16, 2048),
            "cover_memory_cache_max_size_mb": (1, 1024),
            "disk_cache_cleanup_interval": (1, 60),
            "recent_metadata_max_size_mb": (100, 5000),
            "recent_covers_max_size_mb": (100, 10000),
            "persistent_metadata_ttl_hours": (1, 168),
            "musicbrainz_concurrent_searches": (2, 5),
            "discover_queue_size": (1, 20),
            "discover_queue_ttl": (1, 168),
            "discover_queue_polling_interval": (1, 30),
            "discover_queue_seed_artists": (1, 10),
            "discover_queue_wildcard_slots": (0, 10),
            "discover_queue_similar_artists_limit": (5, 50),
            "discover_queue_albums_per_similar": (1, 20),
            "discover_queue_enrich_ttl": (1, 168),
            "discover_queue_lastfm_mbid_max_lookups": (1, 50),
            "frontend_ttl_home": (1, 60),
            "frontend_ttl_discover": (1, 1440),
            "frontend_ttl_library": (1, 60),
            "frontend_ttl_recently_added": (1, 60),
            "frontend_ttl_discover_queue": (60, 10080),
            "frontend_ttl_search": (1, 60),
            "frontend_ttl_local_files_sidebar": (1, 60),
            "frontend_ttl_jellyfin_sidebar": (1, 60),
            "frontend_ttl_playlist_sources": (1, 60),
        }
        for field_name, (minimum, maximum) in ranges.items():
            _validate_range(getattr(self, field_name), field_name, minimum, maximum)

    @staticmethod
    def from_backend(settings: AdvancedSettings) -> "AdvancedSettingsFrontend":
        return AdvancedSettingsFrontend(
            cache_ttl_album_library=settings.cache_ttl_album_library // 3600,
            cache_ttl_album_non_library=settings.cache_ttl_album_non_library // 3600,
            cache_ttl_artist_library=settings.cache_ttl_artist_library // 3600,
            cache_ttl_artist_non_library=settings.cache_ttl_artist_non_library // 3600,
            cache_ttl_artist_discovery_library=settings.cache_ttl_artist_discovery_library // 3600,
            cache_ttl_artist_discovery_non_library=settings.cache_ttl_artist_discovery_non_library // 3600,
            cache_ttl_search=settings.cache_ttl_search // 60,
            cache_ttl_local_files_recently_added=settings.cache_ttl_local_files_recently_added // 60,
            cache_ttl_local_files_storage_stats=settings.cache_ttl_local_files_storage_stats // 60,
            cache_ttl_jellyfin_recently_played=settings.cache_ttl_jellyfin_recently_played // 60,
            cache_ttl_jellyfin_favorites=settings.cache_ttl_jellyfin_favorites // 60,
            cache_ttl_jellyfin_genres=settings.cache_ttl_jellyfin_genres // 60,
            cache_ttl_jellyfin_library_stats=settings.cache_ttl_jellyfin_library_stats // 60,
            http_timeout=settings.http_timeout,
            http_connect_timeout=settings.http_connect_timeout,
            http_max_connections=settings.http_max_connections,
            batch_artist_images=settings.batch_artist_images,
            batch_albums=settings.batch_albums,
            delay_artist=settings.delay_artist,
            delay_albums=settings.delay_albums,
            artist_discovery_warm_interval=settings.artist_discovery_warm_interval // 60,
            artist_discovery_warm_delay=settings.artist_discovery_warm_delay,
            artist_discovery_precache_delay=settings.artist_discovery_precache_delay,
            memory_cache_max_entries=settings.memory_cache_max_entries,
            memory_cache_cleanup_interval=settings.memory_cache_cleanup_interval,
            cover_memory_cache_max_entries=settings.cover_memory_cache_max_entries,
            cover_memory_cache_max_size_mb=settings.cover_memory_cache_max_size_mb,
            disk_cache_cleanup_interval=settings.disk_cache_cleanup_interval // 60,
            recent_metadata_max_size_mb=settings.recent_metadata_max_size_mb,
            recent_covers_max_size_mb=settings.recent_covers_max_size_mb,
            persistent_metadata_ttl_hours=settings.persistent_metadata_ttl_hours,
            musicbrainz_concurrent_searches=settings.musicbrainz_concurrent_searches,
            discover_queue_size=settings.discover_queue_size,
            discover_queue_ttl=settings.discover_queue_ttl // 3600,
            discover_queue_auto_generate=settings.discover_queue_auto_generate,
            discover_queue_polling_interval=settings.discover_queue_polling_interval // 1000,
            discover_queue_warm_cycle_build=settings.discover_queue_warm_cycle_build,
            discover_queue_seed_artists=settings.discover_queue_seed_artists,
            discover_queue_wildcard_slots=settings.discover_queue_wildcard_slots,
            discover_queue_similar_artists_limit=settings.discover_queue_similar_artists_limit,
            discover_queue_albums_per_similar=settings.discover_queue_albums_per_similar,
            discover_queue_enrich_ttl=settings.discover_queue_enrich_ttl // 3600,
            discover_queue_lastfm_mbid_max_lookups=settings.discover_queue_lastfm_mbid_max_lookups,
            frontend_ttl_home=settings.frontend_ttl_home // 60000,
            frontend_ttl_discover=settings.frontend_ttl_discover // 60000,
            frontend_ttl_library=settings.frontend_ttl_library // 60000,
            frontend_ttl_recently_added=settings.frontend_ttl_recently_added // 60000,
            frontend_ttl_discover_queue=settings.frontend_ttl_discover_queue // 60000,
            frontend_ttl_search=settings.frontend_ttl_search // 60000,
            frontend_ttl_local_files_sidebar=settings.frontend_ttl_local_files_sidebar // 60000,
            frontend_ttl_jellyfin_sidebar=settings.frontend_ttl_jellyfin_sidebar // 60000,
            frontend_ttl_playlist_sources=settings.frontend_ttl_playlist_sources // 60000,
        )

    def to_backend(self) -> AdvancedSettings:
        return AdvancedSettings(
            cache_ttl_album_library=self.cache_ttl_album_library * 3600,
            cache_ttl_album_non_library=self.cache_ttl_album_non_library * 3600,
            cache_ttl_artist_library=self.cache_ttl_artist_library * 3600,
            cache_ttl_artist_non_library=self.cache_ttl_artist_non_library * 3600,
            cache_ttl_artist_discovery_library=self.cache_ttl_artist_discovery_library * 3600,
            cache_ttl_artist_discovery_non_library=self.cache_ttl_artist_discovery_non_library * 3600,
            cache_ttl_search=self.cache_ttl_search * 60,
            cache_ttl_local_files_recently_added=self.cache_ttl_local_files_recently_added * 60,
            cache_ttl_local_files_storage_stats=self.cache_ttl_local_files_storage_stats * 60,
            cache_ttl_jellyfin_recently_played=self.cache_ttl_jellyfin_recently_played * 60,
            cache_ttl_jellyfin_favorites=self.cache_ttl_jellyfin_favorites * 60,
            cache_ttl_jellyfin_genres=self.cache_ttl_jellyfin_genres * 60,
            cache_ttl_jellyfin_library_stats=self.cache_ttl_jellyfin_library_stats * 60,
            http_timeout=self.http_timeout,
            http_connect_timeout=self.http_connect_timeout,
            http_max_connections=self.http_max_connections,
            batch_artist_images=self.batch_artist_images,
            batch_albums=self.batch_albums,
            delay_artist=self.delay_artist,
            delay_albums=self.delay_albums,
            artist_discovery_warm_interval=self.artist_discovery_warm_interval * 60,
            artist_discovery_warm_delay=self.artist_discovery_warm_delay,
            artist_discovery_precache_delay=self.artist_discovery_precache_delay,
            memory_cache_max_entries=self.memory_cache_max_entries,
            memory_cache_cleanup_interval=self.memory_cache_cleanup_interval,
            cover_memory_cache_max_entries=self.cover_memory_cache_max_entries,
            cover_memory_cache_max_size_mb=self.cover_memory_cache_max_size_mb,
            disk_cache_cleanup_interval=self.disk_cache_cleanup_interval * 60,
            recent_metadata_max_size_mb=self.recent_metadata_max_size_mb,
            recent_covers_max_size_mb=self.recent_covers_max_size_mb,
            persistent_metadata_ttl_hours=self.persistent_metadata_ttl_hours,
            musicbrainz_concurrent_searches=self.musicbrainz_concurrent_searches,
            discover_queue_size=self.discover_queue_size,
            discover_queue_ttl=self.discover_queue_ttl * 3600,
            discover_queue_auto_generate=self.discover_queue_auto_generate,
            discover_queue_polling_interval=self.discover_queue_polling_interval * 1000,
            discover_queue_warm_cycle_build=self.discover_queue_warm_cycle_build,
            discover_queue_seed_artists=self.discover_queue_seed_artists,
            discover_queue_wildcard_slots=self.discover_queue_wildcard_slots,
            discover_queue_similar_artists_limit=self.discover_queue_similar_artists_limit,
            discover_queue_albums_per_similar=self.discover_queue_albums_per_similar,
            discover_queue_enrich_ttl=self.discover_queue_enrich_ttl * 3600,
            discover_queue_lastfm_mbid_max_lookups=self.discover_queue_lastfm_mbid_max_lookups,
            frontend_ttl_home=self.frontend_ttl_home * 60000,
            frontend_ttl_discover=self.frontend_ttl_discover * 60000,
            frontend_ttl_library=self.frontend_ttl_library * 60000,
            frontend_ttl_recently_added=self.frontend_ttl_recently_added * 60000,
            frontend_ttl_discover_queue=self.frontend_ttl_discover_queue * 60000,
            frontend_ttl_search=self.frontend_ttl_search * 60000,
            frontend_ttl_local_files_sidebar=self.frontend_ttl_local_files_sidebar * 60000,
            frontend_ttl_jellyfin_sidebar=self.frontend_ttl_jellyfin_sidebar * 60000,
            frontend_ttl_playlist_sources=self.frontend_ttl_playlist_sources * 60000,
        )
