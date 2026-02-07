from pydantic import BaseModel, Field, field_validator


class AdvancedSettings(BaseModel):
    
    cache_ttl_album_library: int = Field(
        default=86400,
        ge=3600,
        le=604800,
        description="TTL for library albums in seconds"
    )
    cache_ttl_album_non_library: int = Field(
        default=21600,
        ge=60,
        le=86400,
        description="TTL for non-library albums in seconds"
    )
    cache_ttl_artist_library: int = Field(
        default=21600,
        ge=3600,
        le=604800,
        description="TTL for library artist data in seconds"
    )
    cache_ttl_artist_non_library: int = Field(
        default=21600,
        ge=3600,
        le=604800,
        description="TTL for non-library artist data in seconds"
    )
    cache_ttl_search: int = Field(
        default=3600,
        ge=60,
        le=86400,
        description="TTL for search results in seconds"
    )
    
    http_timeout: int = Field(
        default=10,
        ge=5,
        le=60,
        description="HTTP request timeout in seconds"
    )
    http_connect_timeout: int = Field(
        default=5,
        ge=1,
        le=30,
        description="HTTP connect timeout in seconds"
    )
    http_max_connections: int = Field(
        default=200,
        ge=50,
        le=500,
        description="Maximum HTTP connection pool size"
    )
    
    batch_artist_images: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Concurrent artist image fetches during sync"
    )
    batch_albums: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Concurrent album data fetches during sync"
    )
    delay_artist: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Delay between artist batch operations in seconds"
    )
    delay_albums: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Delay between album batch operations in seconds"
    )
    
    memory_cache_max_entries: int = Field(
        default=10000,
        ge=1000,
        le=100000,
        description="Maximum entries in memory cache"
    )
    memory_cache_cleanup_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Interval for expired entry cleanup in seconds"
    )
    
    disk_cache_cleanup_interval: int = Field(
        default=600,
        ge=60,
        le=3600,
        description="Interval for disk cache cleanup in seconds"
    )
    
    recent_metadata_max_size_mb: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Maximum size for recent metadata cache in MB"
    )
    
    recent_covers_max_size_mb: int = Field(
        default=1024,
        ge=100,
        le=10000,
        description="Maximum size for recent cover cache in MB"
    )
    
    persistent_metadata_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="TTL for persistent metadata cache in hours (primarily for covers)"
    )
    
    musicbrainz_concurrent_searches: int = Field(
        default=3,
        ge=2,
        le=5,
        description="Max concurrent MusicBrainz API requests for parallel search"
    )

    frontend_ttl_home: int = Field(
        default=300000,
        ge=60000,
        le=3600000,
        description="Frontend Home page cache TTL in milliseconds"
    )
    frontend_ttl_discover: int = Field(
        default=1800000,
        ge=60000,
        le=86400000,
        description="Frontend Discover page cache TTL in milliseconds"
    )
    frontend_ttl_library: int = Field(
        default=300000,
        ge=60000,
        le=3600000,
        description="Frontend Library cache TTL in milliseconds"
    )
    frontend_ttl_recently_added: int = Field(
        default=300000,
        ge=60000,
        le=3600000,
        description="Frontend Recently Added cache TTL in milliseconds"
    )
    frontend_ttl_discover_queue: int = Field(
        default=86400000,
        ge=3600000,
        le=604800000,
        description="Frontend Discover Queue cache TTL in milliseconds"
    )
    frontend_ttl_search: int = Field(
        default=300000,
        ge=60000,
        le=3600000,
        description="Frontend Search/Discovery cache TTL in milliseconds"
    )


class FrontendCacheTTLs(BaseModel):
    home: int = Field(default=300000, description="Home page cache TTL in ms")
    discover: int = Field(default=1800000, description="Discover page cache TTL in ms")
    library: int = Field(default=300000, description="Library cache TTL in ms")
    recently_added: int = Field(default=300000, description="Recently Added cache TTL in ms")
    discover_queue: int = Field(default=86400000, description="Discover Queue cache TTL in ms")
    search: int = Field(default=300000, description="Search/Discovery cache TTL in ms")


class AdvancedSettingsFrontend(BaseModel):
    
    cache_ttl_album_library: int = Field(
        default=24,
        ge=1,
        le=168,
        description="TTL for library albums in hours"
    )
    cache_ttl_album_non_library: int = Field(
        default=6,
        ge=1,
        le=24,
        description="TTL for non-library albums in hours"
    )
    cache_ttl_artist_library: int = Field(
        default=6,
        ge=1,
        le=168,
        description="TTL for library artist data in hours"
    )
    cache_ttl_artist_non_library: int = Field(
        default=6,
        ge=1,
        le=168,
        description="TTL for non-library artist data in hours"
    )
    cache_ttl_search: int = Field(
        default=60,
        ge=1,
        le=1440,
        description="TTL for search results in minutes"
    )
    
    http_timeout: int = Field(
        default=10,
        ge=5,
        le=60,
        description="HTTP request timeout in seconds"
    )
    http_connect_timeout: int = Field(
        default=5,
        ge=1,
        le=30,
        description="HTTP connect timeout in seconds"
    )
    http_max_connections: int = Field(
        default=200,
        ge=50,
        le=500,
        description="Maximum HTTP connection pool size"
    )
    
    batch_artist_images: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Concurrent artist image fetches during sync"
    )
    batch_albums: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Concurrent album data fetches during sync"
    )
    delay_artist: float = Field(
        default=0.5,
        ge=0.0,
        le=5.0,
        description="Delay between artist batch operations in seconds"
    )
    delay_albums: float = Field(
        default=1.0,
        ge=0.0,
        le=5.0,
        description="Delay between album batch operations in seconds"
    )
    
    memory_cache_max_entries: int = Field(
        default=10000,
        ge=1000,
        le=100000,
        description="Maximum entries in memory cache"
    )
    memory_cache_cleanup_interval: int = Field(
        default=300,
        ge=60,
        le=3600,
        description="Interval for expired entry cleanup in seconds"
    )
    
    disk_cache_cleanup_interval: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Interval for disk cache cleanup in minutes"
    )
    
    recent_metadata_max_size_mb: int = Field(
        default=500,
        ge=100,
        le=5000,
        description="Maximum size for recent metadata cache in MB"
    )
    
    recent_covers_max_size_mb: int = Field(
        default=1024,
        ge=100,
        le=10000,
        description="Maximum size for recent cover cache in MB"
    )
    
    persistent_metadata_ttl_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="TTL for persistent metadata cache in hours (primarily for covers)"
    )
    
    musicbrainz_concurrent_searches: int = Field(
        default=3,
        ge=2,
        le=5,
        description="Max concurrent MusicBrainz API requests for parallel search"
    )

    frontend_ttl_home: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Home page cache freshness in minutes"
    )
    frontend_ttl_discover: int = Field(
        default=30,
        ge=1,
        le=1440,
        description="Discover page cache freshness in minutes"
    )
    frontend_ttl_library: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Library cache freshness in minutes"
    )
    frontend_ttl_recently_added: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Recently Added cache freshness in minutes"
    )
    frontend_ttl_discover_queue: int = Field(
        default=1440,
        ge=60,
        le=10080,
        description="Discover Queue cache freshness in minutes"
    )
    frontend_ttl_search: int = Field(
        default=5,
        ge=1,
        le=60,
        description="Search/Discovery cache freshness in minutes"
    )

    @field_validator(
        'cache_ttl_album_library', 
        'cache_ttl_album_non_library', 
        'cache_ttl_artist_library',
        'cache_ttl_artist_non_library',
        'cache_ttl_search',
        mode='before'
    )
    @classmethod
    def validate_positive_int(cls, v):
        if v is None:
            return v
        try:
            value = int(float(v))
            if value <= 0:
                raise ValueError(f"Value must be positive, got {value}")
            return value
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid integer value: {v}") from e
    
    @staticmethod
    def from_backend(settings: AdvancedSettings) -> "AdvancedSettingsFrontend":
        return AdvancedSettingsFrontend(
            cache_ttl_album_library=settings.cache_ttl_album_library // 3600,
            cache_ttl_album_non_library=settings.cache_ttl_album_non_library // 3600,
            cache_ttl_artist_library=settings.cache_ttl_artist_library // 3600,
            cache_ttl_artist_non_library=settings.cache_ttl_artist_non_library // 3600,
            cache_ttl_search=settings.cache_ttl_search // 60,
            http_timeout=settings.http_timeout,
            http_connect_timeout=settings.http_connect_timeout,
            http_max_connections=settings.http_max_connections,
            batch_artist_images=settings.batch_artist_images,
            batch_albums=settings.batch_albums,
            delay_artist=settings.delay_artist,
            delay_albums=settings.delay_albums,
            memory_cache_max_entries=settings.memory_cache_max_entries,
            memory_cache_cleanup_interval=settings.memory_cache_cleanup_interval,
            disk_cache_cleanup_interval=settings.disk_cache_cleanup_interval // 60,
            recent_metadata_max_size_mb=settings.recent_metadata_max_size_mb,
            recent_covers_max_size_mb=settings.recent_covers_max_size_mb,
            persistent_metadata_ttl_hours=settings.persistent_metadata_ttl_hours,
            musicbrainz_concurrent_searches=settings.musicbrainz_concurrent_searches,
            frontend_ttl_home=settings.frontend_ttl_home // 60000,
            frontend_ttl_discover=settings.frontend_ttl_discover // 60000,
            frontend_ttl_library=settings.frontend_ttl_library // 60000,
            frontend_ttl_recently_added=settings.frontend_ttl_recently_added // 60000,
            frontend_ttl_discover_queue=settings.frontend_ttl_discover_queue // 60000,
            frontend_ttl_search=settings.frontend_ttl_search // 60000,
        )
    
    def to_backend(self) -> AdvancedSettings:
        return AdvancedSettings(
            cache_ttl_album_library=self.cache_ttl_album_library * 3600,
            cache_ttl_album_non_library=self.cache_ttl_album_non_library * 3600,
            cache_ttl_artist_library=self.cache_ttl_artist_library * 3600,
            cache_ttl_artist_non_library=self.cache_ttl_artist_non_library * 3600,
            cache_ttl_search=self.cache_ttl_search * 60,
            http_timeout=self.http_timeout,
            http_connect_timeout=self.http_connect_timeout,
            http_max_connections=self.http_max_connections,
            batch_artist_images=self.batch_artist_images,
            batch_albums=self.batch_albums,
            delay_artist=self.delay_artist,
            delay_albums=self.delay_albums,
            memory_cache_max_entries=self.memory_cache_max_entries,
            memory_cache_cleanup_interval=self.memory_cache_cleanup_interval,
            disk_cache_cleanup_interval=self.disk_cache_cleanup_interval * 60,
            recent_metadata_max_size_mb=self.recent_metadata_max_size_mb,
            recent_covers_max_size_mb=self.recent_covers_max_size_mb,
            persistent_metadata_ttl_hours=self.persistent_metadata_ttl_hours,
            musicbrainz_concurrent_searches=self.musicbrainz_concurrent_searches,
            frontend_ttl_home=self.frontend_ttl_home * 60000,
            frontend_ttl_discover=self.frontend_ttl_discover * 60000,
            frontend_ttl_library=self.frontend_ttl_library * 60000,
            frontend_ttl_recently_added=self.frontend_ttl_recently_added * 60000,
            frontend_ttl_discover_queue=self.frontend_ttl_discover_queue * 60000,
            frontend_ttl_search=self.frontend_ttl_search * 60000,
        )
