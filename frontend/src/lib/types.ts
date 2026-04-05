export type Artist = {
	title: string;
	musicbrainz_id: string;
	in_library: boolean;
	cover_url?: string | null;
	thumb_url?: string | null;
	fanart_url?: string | null;
	banner_url?: string | null;
	disambiguation?: string | null;
	type_info?: string | null;
	release_group_count?: number | null;
	listen_count?: number | null;
	score?: number;
};

export type Album = {
	title: string;
	artist: string | null;
	year: number | null;
	musicbrainz_id: string;
	in_library: boolean;
	requested?: boolean;
	cover_url?: string | null;
	album_thumb_url?: string | null;
	album_back_url?: string | null;
	album_cdart_url?: string | null;
	album_spine_url?: string | null;
	album_3d_case_url?: string | null;
	album_3d_flat_url?: string | null;
	album_3d_face_url?: string | null;
	album_3d_thumb_url?: string | null;
	type_info?: string | null;
	disambiguation?: string | null;
	track_count?: number | null;
	listen_count?: number | null;
	score?: number;
};

export type LibraryAlbum = {
	artist: string;
	album: string;
	year?: number | null;
	monitored: boolean;
	quality?: string | null;
	cover_url?: string | null;
	musicbrainz_id?: string | null;
	artist_mbid?: string | null;
	date_added?: number | null;
};

export type SearchResults = {
	artists: Artist[];
	albums: Album[];
	top_artist?: Artist | null;
	top_album?: Album | null;
};

export type SuggestResult = {
	type: 'artist' | 'album';
	title: string;
	artist?: string | null;
	year?: number | null;
	musicbrainz_id: string;
	in_library: boolean;
	requested?: boolean;
	disambiguation?: string | null;
	score: number;
};

export type EnrichmentSource = 'listenbrainz' | 'lastfm' | 'none';

export type ArtistEnrichment = {
	musicbrainz_id: string;
	release_group_count?: number | null;
	listen_count?: number | null;
};

export type AlbumEnrichment = {
	musicbrainz_id: string;
	track_count?: number | null;
	listen_count?: number | null;
};

export type ArtistEnrichmentRequest = {
	musicbrainz_id: string;
	name: string;
};

export type AlbumEnrichmentRequest = {
	musicbrainz_id: string;
	artist_name: string;
	album_name: string;
};

export type EnrichmentBatchRequest = {
	artists: ArtistEnrichmentRequest[];
	albums: AlbumEnrichmentRequest[];
};

export type EnrichmentResponse = {
	artists: ArtistEnrichment[];
	albums: AlbumEnrichment[];
	source: EnrichmentSource;
};

export type ReleaseGroup = {
	id: string;
	title: string;
	type?: string;
	year?: number;
	first_release_date?: string;
	in_library: boolean;
	requested?: boolean;
};

export type ExternalLink = {
	type: string;
	url: string;
	label: string;
	category?: string;
};

export type ArtistInfo = {
	name: string;
	musicbrainz_id: string;
	disambiguation?: string | null;
	type?: string | null;
	country?: string | null;
	life_span?: {
		begin?: string | null;
		end?: string | null;
		ended?: boolean;
	} | null;
	description?: string | null;
	image?: string | null;
	fanart_url?: string | null;
	banner_url?: string | null;
	thumb_url?: string | null;
	fanart_url_2?: string | null;
	fanart_url_3?: string | null;
	fanart_url_4?: string | null;
	wide_thumb_url?: string | null;
	logo_url?: string | null;
	clearart_url?: string | null;
	cutout_url?: string | null;
	tags: string[];
	aliases: string[];
	external_links: ExternalLink[];
	in_library: boolean;
	albums: ReleaseGroup[];
	singles: ReleaseGroup[];
	eps: ReleaseGroup[];
	release_group_count?: number;
};

export type ArtistReleases = {
	albums: ReleaseGroup[];
	singles: ReleaseGroup[];
	eps: ReleaseGroup[];
	total_count: number;
	has_more: boolean;
};

export type UserPreferences = {
	primary_types: string[];
	secondary_types: string[];
	release_statuses: string[];
};

export type ReleaseTypeOption = {
	id: string;
	title: string;
	description: string;
};

export type Track = {
	position: number;
	disc_number?: number | null;
	title: string;
	length?: number | null;
	recording_id?: string | null;
};

export type AlbumInfo = {
	title: string;
	musicbrainz_id: string;
	artist_name: string;
	artist_id: string;
	release_date?: string | null;
	year?: number | null;
	type?: string | null;
	label?: string | null;
	barcode?: string | null;
	country?: string | null;
	disambiguation?: string | null;
	tracks: Track[];
	total_tracks: number;
	total_length?: number | null;
	in_library: boolean;
	requested?: boolean;
	cover_url?: string | null;
	album_thumb_url?: string | null;
	album_back_url?: string | null;
	album_cdart_url?: string | null;
	album_spine_url?: string | null;
	album_3d_case_url?: string | null;
	album_3d_flat_url?: string | null;
	album_3d_face_url?: string | null;
	album_3d_thumb_url?: string | null;
};

export type AlbumBasicInfo = {
	title: string;
	musicbrainz_id: string;
	artist_name: string;
	artist_id: string;
	release_date?: string | null;
	year?: number | null;
	type?: string | null;
	disambiguation?: string | null;
	in_library: boolean;
	requested?: boolean;
	cover_url?: string | null;
	album_thumb_url?: string | null;
};

export type AlbumTracksInfo = {
	tracks: Track[];
	total_tracks: number;
	total_length?: number | null;
	label?: string | null;
	barcode?: string | null;
	country?: string | null;
};

export type LidarrConnectionSettings = {
	lidarr_url: string;
	lidarr_api_key: string;
	quality_profile_id: number;
	metadata_profile_id: number;
	root_folder_path: string;
};

export type JellyfinConnectionSettings = {
	jellyfin_url: string;
	api_key: string;
	user_id: string;
	enabled: boolean;
};

export type ListenBrainzConnectionSettings = {
	username: string;
	user_token: string;
	enabled: boolean;
};

export type HomeSettings = {
	cache_ttl_trending: number;
	cache_ttl_personal: number;
};

export type HomeArtist = {
	mbid: string | null;
	name: string;
	image_url: string | null;
	listen_count: number | null;
	in_library: boolean;
};

export type HomeAlbum = {
	mbid: string | null;
	name: string;
	artist_name: string | null;
	artist_mbid: string | null;
	image_url: string | null;
	release_date: string | null;
	listen_count: number | null;
	in_library: boolean;
	requested?: boolean;
};

export type HomeTrack = {
	mbid: string | null;
	name: string;
	artist_name: string | null;
	artist_mbid: string | null;
	album_name: string | null;
	listen_count: number | null;
	listened_at: string | null;
	image_url?: string | null;
};

export type HomeGenre = {
	name: string;
	listen_count: number | null;
	artist_count: number | null;
	artist_mbid: string | null;
};

export type HomeSection = {
	title: string;
	type: 'artists' | 'albums' | 'tracks' | 'genres';
	items: (HomeArtist | HomeAlbum | HomeTrack | HomeGenre)[];
	source: string | null;
	fallback_message: string | null;
	connect_service: string | null;
};

export type ServicePrompt = {
	service: string;
	title: string;
	description: string;
	icon: string;
	color: string;
	features: string[];
};

export type HomeResponse = {
	recently_added: HomeSection | null;
	library_artists: HomeSection | null;
	library_albums: HomeSection | null;
	recommended_artists: HomeSection | null;
	trending_artists: HomeSection | null;
	popular_albums: HomeSection | null;
	recently_played: HomeSection | null;
	top_genres: HomeSection | null;
	genre_list: HomeSection | null;
	fresh_releases: HomeSection | null;
	favorite_artists: HomeSection | null;
	your_top_albums: HomeSection | null;
	weekly_exploration: WeeklyExplorationSection | null;
	service_prompts: ServicePrompt[];
	integration_status: Record<string, boolean>;
	genre_artists: Record<string, string | null>;
	genre_artist_images: Record<string, string | null>;
	discover_preview: DiscoverPreview | null;
};

export type DiscoverPreview = {
	seed_artist: string;
	seed_artist_mbid: string;
	items: HomeArtist[];
};

export type BecauseYouListenTo = {
	seed_artist: string;
	seed_artist_mbid: string;
	listen_count: number;
	section: HomeSection;
	banner_url?: string | null;
	wide_thumb_url?: string | null;
	fanart_url?: string | null;
};

export type WeeklyExplorationTrack = {
	title: string;
	artist_name: string;
	album_name: string;
	recording_mbid: string | null;
	artist_mbid: string | null;
	release_group_mbid: string | null;
	cover_url: string | null;
	duration_ms: number | null;
};

export type WeeklyExplorationSection = {
	title: string;
	playlist_date: string;
	tracks: WeeklyExplorationTrack[];
	source_url: string;
};

export type DiscoverResponse = {
	because_you_listen_to: BecauseYouListenTo[];
	discover_queue_enabled: boolean;
	fresh_releases: HomeSection | null;
	missing_essentials: HomeSection | null;
	rediscover: HomeSection | null;
	artists_you_might_like: HomeSection | null;
	popular_in_your_genres: HomeSection | null;
	genre_list: HomeSection | null;
	globally_trending: HomeSection | null;
	weekly_exploration: WeeklyExplorationSection | null;
	lastfm_weekly_artist_chart: HomeSection | null;
	lastfm_weekly_album_chart: HomeSection | null;
	lastfm_recent_scrobbles: HomeSection | null;
	genre_artists: Record<string, string | null>;
	genre_artist_images: Record<string, string | null>;
	integration_status: Record<string, boolean>;
	service_prompts: ServicePrompt[];
	refreshing: boolean;
};

export type QualityProfile = {
	id: number;
	name: string;
};

export type MetadataProfile = {
	id: number;
	name: string;
};

export type RootFolder = {
	id: string;
	path: string;
};

export type LidarrVerifyResponse = {
	success: boolean;
	message: string;
	quality_profiles: QualityProfile[];
	metadata_profiles: MetadataProfile[];
	root_folders: RootFolder[];
};

export type LidarrMetadataProfilePreferences = {
	profile_id: number;
	profile_name: string;
	primary_types: string[];
	secondary_types: string[];
	release_statuses: string[];
};

export type TrendingTimeRange = {
	range_key: string;
	label: string;
	featured: HomeArtist | null;
	items: HomeArtist[];
	total_count: number;
};

export type TrendingArtistsResponse = {
	this_week: TrendingTimeRange;
	this_month: TrendingTimeRange;
	this_year: TrendingTimeRange;
	all_time: TrendingTimeRange;
};

export type PopularTimeRange = {
	range_key: string;
	label: string;
	featured: HomeAlbum | null;
	items: HomeAlbum[];
	total_count: number;
};

export type PopularAlbumsResponse = {
	this_week: PopularTimeRange;
	this_month: PopularTimeRange;
	this_year: PopularTimeRange;
	all_time: PopularTimeRange;
};

export type TrendingArtistsRangeResponse = {
	range_key: string;
	label: string;
	items: HomeArtist[];
	offset: number;
	limit: number;
	has_more: boolean;
};

export type PopularAlbumsRangeResponse = {
	range_key: string;
	label: string;
	items: HomeAlbum[];
	offset: number;
	limit: number;
	has_more: boolean;
};

export type GenreLibrarySection = {
	artists: HomeArtist[];
	albums: HomeAlbum[];
	artist_count: number;
	album_count: number;
};

export type GenrePopularSection = {
	artists: HomeArtist[];
	albums: HomeAlbum[];
	has_more_artists: boolean;
	has_more_albums: boolean;
};

export type GenreDetailResponse = {
	genre: string;
	library: GenreLibrarySection | null;
	popular: GenrePopularSection | null;
	artists: HomeArtist[];
	total_count: number | null;
};

export type SimilarArtist = {
	musicbrainz_id: string;
	name: string;
	listen_count: number;
	in_library: boolean;
	image_url?: string | null;
};

export type SimilarArtistsResponse = {
	similar_artists: SimilarArtist[];
	source: string;
	configured: boolean;
};

export type TopSong = {
	recording_mbid?: string | null;
	release_group_mbid?: string | null;
	original_release_mbid?: string | null;
	title: string;
	artist_name: string;
	release_name?: string | null;
	listen_count: number;
	disc_number?: number | null;
	track_number?: number | null;
};

export type TopSongsResponse = {
	songs: TopSong[];
	source: string;
	configured: boolean;
};

export type ResolvedTrack = {
	release_group_mbid?: string | null;
	disc_number?: number | null;
	track_number?: number | null;
	source?: string | null;
	track_source_id?: string | null;
	stream_url?: string | null;
	format?: string | null;
	duration?: number | null;
};

export type TopAlbum = {
	release_group_mbid?: string | null;
	title: string;
	artist_name: string;
	year?: number | null;
	listen_count: number;
	in_library: boolean;
	requested?: boolean;
	cover_url?: string | null;
};

export type TopAlbumsResponse = {
	albums: TopAlbum[];
	source: string;
	configured: boolean;
};

export type DiscoveryAlbum = {
	musicbrainz_id: string;
	title: string;
	artist_name: string;
	artist_id?: string | null;
	year?: number | null;
	in_library: boolean;
	requested?: boolean;
	cover_url?: string | null;
};

export type SimilarAlbumsResponse = {
	albums: DiscoveryAlbum[];
	source: string;
	configured: boolean;
};

export type DiscoverQueueItemLight = {
	release_group_mbid: string;
	album_name: string;
	artist_name: string;
	artist_mbid: string;
	cover_url: string | null;
	recommendation_reason: string;
	is_wildcard: boolean;
	in_library: boolean;
};

export type DiscoverQueueEnrichment = {
	artist_mbid: string | null;
	release_date: string | null;
	country: string | null;
	tags: string[];
	youtube_url: string | null;
	youtube_search_url: string;
	youtube_search_available: boolean;
	artist_description: string | null;
	listen_count: number | null;
};

export type YouTubeSearchResponse = {
	video_id: string | null;
	embed_url: string | null;
	error: string | null;
	cached: boolean;
};

export type YouTubeQuotaStatus = {
	used: number;
	limit: number;
	remaining: number;
	date: string;
};

export type TrackCacheCheckItem = {
	artist: string;
	track: string;
	cached: boolean;
};

export type DiscoverQueueItemFull = DiscoverQueueItemLight & {
	enrichment?: DiscoverQueueEnrichment;
};

export type DiscoverQueueResponse = {
	items: DiscoverQueueItemFull[];
	queue_id: string;
};

export type QueueStatusResponse = {
	status: 'idle' | 'building' | 'ready' | 'error';
	source: string;
	queue_id?: string;
	item_count?: number;
	built_at?: number;
	stale?: boolean;
	error?: string;
};

export type QueueGenerateResponse = {
	action: 'started' | 'already_building' | 'already_ready';
	status: string;
	source: string;
	queue_id?: string;
	item_count?: number;
	built_at?: number;
	stale?: boolean;
	error?: string;
};

export type MoreByArtistResponse = {
	albums: DiscoveryAlbum[];
	artist_name: string;
};

export type YouTubeLink = {
	album_id: string;
	video_id: string | null;
	album_name: string;
	artist_name: string;
	embed_url: string | null;
	cover_url: string | null;
	created_at: string;
	is_manual: boolean;
	track_count: number;
};

export type YouTubeLinkResponse = {
	link: YouTubeLink;
	quota: YouTubeQuotaStatus;
};

export type YouTubeLinkGenerateRequest = {
	artist_name: string;
	album_name: string;
	album_id: string;
	cover_url?: string | null;
};

export type YouTubeTrackLink = {
	album_id: string;
	track_number: number;
	disc_number?: number | null;
	track_name: string;
	video_id: string;
	artist_name: string;
	embed_url: string;
	created_at: string;
	album_name?: string;
};

export type YouTubeTrackLinkResponse = {
	track_link: YouTubeTrackLink;
	quota: YouTubeQuotaStatus;
};

export type YouTubeTrackLinkBatchResponse = {
	track_links: YouTubeTrackLink[];
	failed: {
		track_number: number;
		disc_number?: number | null;
		track_name: string;
		reason: string;
	}[];
	quota: YouTubeQuotaStatus;
};

export type StatusMessage = {
	title?: string | null;
	messages: string[];
};

export type ActiveRequestItem = {
	musicbrainz_id: string;
	artist_name: string;
	album_title: string;
	artist_mbid?: string | null;
	year?: number | null;
	cover_url?: string | null;
	requested_at: string;
	status: string;
	progress?: number | null;
	eta?: string | null;
	size?: number | null;
	size_remaining?: number | null;
	download_status?: string | null;
	download_state?: string | null;
	status_messages?: StatusMessage[] | null;
	error_message?: string | null;
	lidarr_queue_id?: number | null;
	quality?: string | null;
	protocol?: string | null;
	download_client?: string | null;
};

export type RequestHistoryItem = {
	musicbrainz_id: string;
	artist_name: string;
	album_title: string;
	artist_mbid?: string | null;
	year?: number | null;
	cover_url?: string | null;
	requested_at: string;
	completed_at?: string | null;
	status: string;
	in_library: boolean;
};

export type ActiveRequestsResponse = {
	items: ActiveRequestItem[];
	count: number;
};

export type RequestHistoryResponse = {
	items: RequestHistoryItem[];
	total: number;
	page: number;
	page_size: number;
	total_pages: number;
};

export type JellyfinTrackInfo = {
	jellyfin_id: string;
	title: string;
	track_number: number;
	disc_number?: number | null;
	duration_seconds: number;
	album_name: string;
	artist_name: string;
	codec?: string | null;
	bitrate?: number | null;
};

export type JellyfinAlbumMatch = {
	found: boolean;
	jellyfin_album_id?: string | null;
	tracks: JellyfinTrackInfo[];
};

export type JellyfinAlbumSummary = {
	jellyfin_id: string;
	name: string;
	artist_name: string;
	year?: number | null;
	track_count: number;
	image_url?: string | null;
	musicbrainz_id?: string | null;
	artist_musicbrainz_id?: string | null;
};

export type JellyfinPaginatedResponse = {
	items: JellyfinAlbumSummary[];
	total: number;
	offset: number;
	limit: number;
};

export type JellyfinSearchResponse = {
	albums: JellyfinAlbumSummary[];
	artists: JellyfinArtistSummary[];
	tracks: JellyfinTrackInfo[];
};

export type JellyfinLibraryStats = {
	total_tracks: number;
	total_albums: number;
	total_artists: number;
};

export type JellyfinArtistSummary = {
	jellyfin_id: string;
	name: string;
	image_url?: string | null;
	album_count: number;
	musicbrainz_id?: string | null;
};

export type NavidromeConnectionSettings = {
	navidrome_url: string;
	username: string;
	password: string;
	enabled: boolean;
};

export type NavidromeTrackInfo = {
	navidrome_id: string;
	title: string;
	track_number: number;
	disc_number?: number | null;
	duration_seconds: number;
	album_name: string;
	artist_name: string;
	codec?: string | null;
	bitrate?: number | null;
};

export type NavidromeAlbumSummary = {
	navidrome_id: string;
	name: string;
	artist_name: string;
	year?: number | null;
	track_count: number;
	image_url?: string | null;
	musicbrainz_id?: string | null;
	artist_musicbrainz_id?: string | null;
};

export type NavidromeAlbumDetail = NavidromeAlbumSummary & {
	tracks: NavidromeTrackInfo[];
};

export type NavidromeAlbumMatch = {
	found: boolean;
	navidrome_album_id?: string | null;
	tracks: NavidromeTrackInfo[];
};

export type NavidromeArtistSummary = {
	navidrome_id: string;
	name: string;
	image_url?: string | null;
	album_count: number;
	musicbrainz_id?: string | null;
};

export type NavidromeSearchResponse = {
	albums: NavidromeAlbumSummary[];
	artists: NavidromeArtistSummary[];
	tracks: NavidromeTrackInfo[];
};

export type NavidromeLibraryStats = {
	total_tracks: number;
	total_albums: number;
	total_artists: number;
};

export type NavidromePaginatedResponse = {
	items: NavidromeAlbumSummary[];
	total: number;
};

export type LocalTrackInfo = {
	track_file_id: number;
	title: string;
	track_number: number;
	disc_number?: number | null;
	duration_seconds?: number | null;
	size_bytes: number;
	format: string;
	bitrate?: number | null;
	date_added?: string | null;
};

export type LocalAlbumMatch = {
	found: boolean;
	tracks: LocalTrackInfo[];
	total_size_bytes: number;
	primary_format?: string | null;
};

export type LocalAlbumSummary = {
	lidarr_album_id: number;
	musicbrainz_id: string;
	name: string;
	artist_name: string;
	artist_mbid?: string | null;
	year?: number | null;
	track_count: number;
	total_size_bytes: number;
	primary_format?: string | null;
	cover_url?: string | null;
	date_added?: string | null;
};

export type LocalPaginatedResponse = {
	items: LocalAlbumSummary[];
	total: number;
	offset: number;
	limit: number;
};

export type FormatInfo = {
	count: number;
	size_bytes: number;
	size_human: string;
};

export type LocalStorageStats = {
	total_tracks: number;
	total_albums: number;
	total_artists: number;
	total_size_bytes: number;
	total_size_human: string;
	disk_free_bytes: number;
	disk_free_human: string;
	format_breakdown: Record<string, FormatInfo>;
};

export type LocalFilesConnectionSettings = {
	enabled: boolean;
	music_path: string;
	lidarr_root_path: string;
};

export type LastFmConnectionSettings = {
	api_key: string;
	shared_secret: string;
	session_key: string;
	username: string;
	enabled: boolean;
};

export type LastFmConnectionSettingsResponse = {
	api_key: string;
	shared_secret: string;
	session_key: string;
	username: string;
	enabled: boolean;
};

export type LastFmVerifyResponse = {
	valid: boolean;
	message: string;
};

export type LastFmAuthTokenResponse = {
	token: string;
	auth_url: string;
};

export type LastFmAuthSessionResponse = {
	username: string;
	success: boolean;
	message: string;
};

export type ScrobbleSettings = {
	scrobble_to_lastfm: boolean;
	scrobble_to_listenbrainz: boolean;
};

export type NowPlayingSubmission = {
	track_name: string;
	artist_name: string;
	album_name: string;
	duration_ms: number;
	mbid?: string;
};

export type ScrobbleSubmission = {
	track_name: string;
	artist_name: string;
	album_name: string;
	timestamp: number;
	duration_ms: number;
	mbid?: string;
};

export type ServiceResult = {
	success: boolean;
	error?: string;
};

export type ScrobbleResponse = {
	accepted: boolean;
	services: Record<string, ServiceResult>;
};

export type LastFmTag = {
	name: string;
	url?: string | null;
};

export type LastFmSimilarArtistDetail = {
	name: string;
	mbid?: string | null;
	match: number;
	url?: string | null;
};

export type LastFmArtistEnrichment = {
	bio?: string | null;
	summary?: string | null;
	tags: LastFmTag[];
	listeners: number;
	playcount: number;
	similar_artists: LastFmSimilarArtistDetail[];
	url?: string | null;
};

export type LastFmAlbumEnrichment = {
	summary?: string | null;
	tags: LastFmTag[];
	listeners: number;
	playcount: number;
	url?: string | null;
};
