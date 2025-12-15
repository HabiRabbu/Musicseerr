export type Artist = {
	title: string;
	musicbrainz_id: string;
	in_library: boolean;
	cover_url?: string | null;
};

export type Album = {
	title: string;
	artist: string | null;
	year: number | null;
	musicbrainz_id: string;
	in_library: boolean;
	cover_url?: string | null;
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
};

export type ReleaseGroup = {
	id: string;
	title: string;
	type?: string;
	year?: number;
	first_release_date?: string;
	in_library: boolean;
};

export type ExternalLink = {
	type: string;
	url: string;
	label: string;
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

export type SoularrConnectionSettings = {
	soularr_url: string;
	soularr_api_key: string;
	trigger_soularr: boolean;
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
};

export type HomeTrack = {
	mbid: string | null;
	name: string;
	artist_name: string | null;
	artist_mbid: string | null;
	album_name: string | null;
	listen_count: number | null;
	listened_at: string | null;
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
	service_prompts: ServicePrompt[];
	integration_status: Record<string, boolean>;
	genre_artists: Record<string, string | null>;
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