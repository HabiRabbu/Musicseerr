from pydantic import BaseModel, Field


class HomeArtist(BaseModel):
    mbid: str | None = Field(default=None, description="MusicBrainz artist ID")
    name: str = Field(description="Artist name")
    image_url: str | None = Field(default=None, description="Artist image URL")
    listen_count: int | None = Field(default=None, description="Total listen count")
    in_library: bool = Field(default=False, description="Whether artist is in Lidarr library")
    source: str | None = Field(default=None, description="Data source (listenbrainz, lastfm, etc.)")


class HomeAlbum(BaseModel):
    mbid: str | None = Field(default=None, description="MusicBrainz release group ID")
    name: str = Field(description="Album name")
    artist_name: str | None = Field(default=None, description="Artist name")
    artist_mbid: str | None = Field(default=None, description="MusicBrainz artist ID")
    image_url: str | None = Field(default=None, description="Album cover URL")
    release_date: str | None = Field(default=None, description="Release date")
    listen_count: int | None = Field(default=None, description="Total listen count")
    in_library: bool = Field(default=False, description="Whether album is in library")
    requested: bool = Field(default=False, description="Whether album is requested/in queue")
    source: str | None = Field(default=None, description="Data source (listenbrainz, lastfm, etc.)")


class HomeTrack(BaseModel):
    mbid: str | None = Field(default=None, description="MusicBrainz recording ID")
    name: str = Field(description="Track name")
    artist_name: str | None = Field(default=None, description="Artist name")
    artist_mbid: str | None = Field(default=None, description="MusicBrainz artist ID")
    album_name: str | None = Field(default=None, description="Album name")
    listen_count: int | None = Field(default=None, description="Listen count")
    listened_at: str | None = Field(default=None, description="When the track was listened to")
    image_url: str | None = Field(default=None, description="Track or album image URL")


class HomeGenre(BaseModel):
    name: str = Field(description="Genre name")
    listen_count: int | None = Field(default=None, description="Listen count for this genre")
    artist_count: int | None = Field(default=None, description="Number of artists in this genre")
    artist_mbid: str | None = Field(default=None, description="MBID of a representative artist for this genre")


class HomeSection(BaseModel):
    title: str = Field(description="Section title")
    type: str = Field(description="Section type: artists, albums, tracks, genres")
    items: list[HomeArtist | HomeAlbum | HomeTrack | HomeGenre] = Field(
        default_factory=list,
        description="Section items"
    )
    source: str | None = Field(
        default=None,
        description="Data source: listenbrainz, jellyfin, lidarr, or None for fallback"
    )
    fallback_message: str | None = Field(
        default=None,
        description="Message to show when no data is available"
    )
    connect_service: str | None = Field(
        default=None,
        description="Service to connect to enable this section"
    )


class ServicePrompt(BaseModel):
    service: str = Field(description="Service identifier: listenbrainz, jellyfin")
    title: str = Field(description="Prompt title")
    description: str = Field(description="Prompt description")
    icon: str = Field(description="Emoji icon")
    color: str = Field(description="Color theme: primary, secondary, accent")
    features: list[str] = Field(default_factory=list, description="List of features")


class HomeResponse(BaseModel):
    recently_added: HomeSection | None = Field(
        default=None, description="Recently added albums from Lidarr"
    )
    library_artists: HomeSection | None = Field(
        default=None, description="Artists in your library"
    )
    library_albums: HomeSection | None = Field(
        default=None, description="Albums in your library"
    )
    recommended_artists: HomeSection | None = Field(
        default=None, description="Recommended artists based on listening history"
    )
    trending_artists: HomeSection | None = Field(
        default=None, description="Trending artists globally"
    )
    popular_albums: HomeSection | None = Field(
        default=None, description="Popular albums right now"
    )
    recently_played: HomeSection | None = Field(
        default=None, description="Recently played tracks"
    )
    top_genres: HomeSection | None = Field(
        default=None, description="User's top genres"
    )
    genre_list: HomeSection | None = Field(
        default=None, description="List of available genres"
    )
    fresh_releases: HomeSection | None = Field(
        default=None, description="New releases from followed artists"
    )
    favorite_artists: HomeSection | None = Field(
        default=None, description="User's favorite artists"
    )
    your_top_albums: HomeSection | None = Field(
        default=None, description="User's personal top albums from listening history"
    )
    service_prompts: list[ServicePrompt] = Field(
        default_factory=list,
        description="Prompts for connecting additional services"
    )
    integration_status: dict[str, bool] = Field(
        default_factory=dict,
        description="Status of integrations: listenbrainz, jellyfin, lidarr"
    )
    genre_artists: dict[str, str | None] = Field(
        default_factory=dict,
        description="Map of genre name to representative artist MBID"
    )
    discover_preview: "DiscoverPreview | None" = Field(
        default=None,
        description="Preview teaser from discover cache for home page"
    )


class DiscoverPreview(BaseModel):
    seed_artist: str = Field(description="Name of the seed artist")
    seed_artist_mbid: str = Field(description="MusicBrainz ID of the seed artist")
    items: list[HomeArtist] = Field(default_factory=list, description="Preview artist items")


class GenreDetailRequest(BaseModel):
    genre: str = Field(description="Genre name to fetch details for")
    limit: int = Field(default=50, ge=1, le=200, description="Number of artists to return")


class GenreLibrarySection(BaseModel):
    artists: list[HomeArtist] = Field(default_factory=list, description="Library artists in this genre")
    albums: list[HomeAlbum] = Field(default_factory=list, description="Library albums in this genre")
    artist_count: int = Field(default=0, description="Total library artists in genre")
    album_count: int = Field(default=0, description="Total library albums in genre")


class GenrePopularSection(BaseModel):
    artists: list[HomeArtist] = Field(default_factory=list, description="Popular artists in this genre")
    albums: list[HomeAlbum] = Field(default_factory=list, description="Popular albums in this genre")
    has_more_artists: bool = Field(default=False, description="Whether more artists can be loaded")
    has_more_albums: bool = Field(default=False, description="Whether more albums can be loaded")


class GenreDetailResponse(BaseModel):
    genre: str = Field(description="Genre name")
    library: GenreLibrarySection | None = Field(default=None, description="Library items in this genre")
    popular: GenrePopularSection | None = Field(default=None, description="Popular items in this genre")
    artists: list[HomeArtist] = Field(default_factory=list, description="Artists in this genre (legacy)")
    total_count: int | None = Field(default=None, description="Total number of artists (legacy)")


class TrendingTimeRange(BaseModel):
    range_key: str = Field(description="Range key: this_week, this_month, this_year, all_time")
    label: str = Field(description="Human readable label")
    featured: HomeArtist | None = Field(default=None, description="Featured top artist")
    items: list[HomeArtist] = Field(default_factory=list, description="Trending artists")
    total_count: int = Field(default=0, description="Total count of items")


class TrendingArtistsResponse(BaseModel):
    this_week: TrendingTimeRange = Field(description="This week's trending artists")
    this_month: TrendingTimeRange = Field(description="This month's trending artists")
    this_year: TrendingTimeRange = Field(description="This year's trending artists")
    all_time: TrendingTimeRange = Field(description="All time trending artists")


class PopularTimeRange(BaseModel):
    range_key: str = Field(description="Range key: this_week, this_month, this_year, all_time")
    label: str = Field(description="Human readable label")
    featured: HomeAlbum | None = Field(default=None, description="Featured top album")
    items: list[HomeAlbum] = Field(default_factory=list, description="Popular albums")
    total_count: int = Field(default=0, description="Total count of items")


class PopularAlbumsResponse(BaseModel):
    this_week: PopularTimeRange = Field(description="This week's popular albums")
    this_month: PopularTimeRange = Field(description="This month's popular albums")
    this_year: PopularTimeRange = Field(description="This year's popular albums")
    all_time: PopularTimeRange = Field(description="All time popular albums")


class TrendingArtistsRangeResponse(BaseModel):
    range_key: str = Field(description="Range key used")
    label: str = Field(description="Human readable label")
    items: list[HomeArtist] = Field(default_factory=list, description="Trending artists")
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(default=25, description="Items per page")
    has_more: bool = Field(default=False, description="Whether more items exist")


class PopularAlbumsRangeResponse(BaseModel):
    range_key: str = Field(description="Range key used")
    label: str = Field(description="Human readable label")
    items: list[HomeAlbum] = Field(default_factory=list, description="Popular albums")
    offset: int = Field(default=0, description="Current offset")
    limit: int = Field(default=25, description="Items per page")
    has_more: bool = Field(default=False, description="Whether more items exist")
