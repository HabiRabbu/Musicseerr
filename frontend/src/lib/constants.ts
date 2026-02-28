export const CACHE_KEY_GROUPS = {
	core: {
		LIBRARY_MBIDS: 'musicseerr_library_mbids',
		RECENTLY_ADDED: 'musicseerr_recently_added',
		HOME_CACHE: 'musicseerr_home_cache',
		DISCOVER_CACHE: 'musicseerr_discover_cache',
		DISCOVER_QUEUE: 'musicseerr_discover_queue',
		SEARCH: 'musicseerr_search_cache'
	},
	library: {
		LOCAL_FILES_SIDEBAR: 'musicseerr_local_files_sidebar',
		JELLYFIN_SIDEBAR: 'musicseerr_jellyfin_sidebar',
		JELLYFIN_ALBUMS_LIST: 'musicseerr_jellyfin_albums_list',
		LOCAL_FILES_ALBUMS_LIST: 'musicseerr_local_files_albums_list'
	},
	detail: {
		ALBUM_BASIC_CACHE: 'musicseerr_album_basic_cache',
		ALBUM_TRACKS_CACHE: 'musicseerr_album_tracks_cache',
		ALBUM_DISCOVERY_CACHE: 'musicseerr_album_discovery_cache',
		ALBUM_LASTFM_CACHE: 'musicseerr_album_lastfm_cache',
		ARTIST_BASIC_CACHE: 'musicseerr_artist_basic_cache',
		ARTIST_EXTENDED_CACHE: 'musicseerr_artist_extended_cache',
		ARTIST_LASTFM_CACHE: 'musicseerr_artist_lastfm_cache'
	},
	charts: {
		TIME_RANGE_OVERVIEW_CACHE: 'musicseerr_time_range_overview_cache',
		GENRE_DETAIL_CACHE: 'musicseerr_genre_detail_cache'
	}
} as const;

export const CACHE_KEYS = {
	...CACHE_KEY_GROUPS.core,
	...CACHE_KEY_GROUPS.library,
	...CACHE_KEY_GROUPS.detail,
	...CACHE_KEY_GROUPS.charts
} as const;

export const PAGE_SOURCE_KEYS = {
	home: 'musicseerr_source_home',
	discover: 'musicseerr_source_discover',
	artist: 'musicseerr_source_artist',
	trending: 'musicseerr_source_trending',
	popular: 'musicseerr_source_popular',
	yourTop: 'musicseerr_source_your_top'
} as const;

export const CACHE_TTL_GROUPS = {
	core: {
		DEFAULT: 5 * 60 * 1000,
		LIBRARY: 5 * 60 * 1000,
		RECENTLY_ADDED: 5 * 60 * 1000,
		HOME: 5 * 60 * 1000,
		DISCOVER: 30 * 60 * 1000,
		DISCOVER_QUEUE: 24 * 60 * 60 * 1000,
		SEARCH: 5 * 60 * 1000
	},
	library: {
		LOCAL_FILES_SIDEBAR: 2 * 60 * 1000,
		JELLYFIN_SIDEBAR: 2 * 60 * 1000,
		JELLYFIN_ALBUMS_LIST: 2 * 60 * 1000,
		LOCAL_FILES_ALBUMS_LIST: 2 * 60 * 1000
	},
	detail: {
		ALBUM_DETAIL_BASIC: 5 * 60 * 1000,
		ALBUM_DETAIL_TRACKS: 15 * 60 * 1000,
		ALBUM_DETAIL_DISCOVERY: 30 * 60 * 1000,
		ALBUM_DETAIL_LASTFM: 30 * 60 * 1000,
		ARTIST_DETAIL_BASIC: 5 * 60 * 1000,
		ARTIST_DETAIL_EXTENDED: 30 * 60 * 1000,
		ARTIST_DETAIL_LASTFM: 30 * 60 * 1000
	},
	charts: {
		TIME_RANGE_OVERVIEW: 2 * 60 * 1000,
		GENRE_DETAIL: 5 * 60 * 1000
	}
} as const;

export const CACHE_TTL = {
	...CACHE_TTL_GROUPS.core,
	...CACHE_TTL_GROUPS.library,
	...CACHE_TTL_GROUPS.detail,
	...CACHE_TTL_GROUPS.charts
} as const;

export const API_SIZES = {
	XS: 250,
	SM: 250,
	MD: 250,
	LG: 500,
	XL: 500,
	HERO: 500,
	FULL: 500
} as const;

export const BATCH_SIZES = {
	RELEASES: 50,
	SEARCH_RESULTS: 24,
	COVER_PREFETCH: 12
} as const;

export const TOAST_DURATION = 2000;

export const SCROLL_THRESHOLD = 10;

export const CANVAS_SAMPLE_SIZE = 50;

export const IMAGE_PIXEL_SAMPLE_STEP = 16;

export const ALPHA_THRESHOLD = 128;

export const PLACEHOLDER_COLORS = {
	DARK: '#0d120a',
	MEDIUM: '#161d12',
	LIGHT: '#1F271B'
} as const;

export const STATUS_COLORS = {
	REQUESTED: '#F59E0B'
} as const;

export const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const YOUTUBE_PLAYER_ELEMENT_ID = 'yt-player-embed';

export const API = {
	artist: {
		basic: (id: string) => `/api/artist/${id}`,
		extended: (id: string) => `/api/artist/${id}/extended`,
		releases: (id: string, offset: number, limit: number) =>
			`/api/artist/${id}/releases?offset=${offset}&limit=${limit}`
	},
	album: {
		basic: (id: string) => `/api/album/${id}`,
		tracks: (id: string) => `/api/album/${id}/tracks`
	},
	library: {
		mbids: () => '/api/library/mbids',
		albums: () => '/api/library/albums',
		artists: () => '/api/library/artists',
		removeAlbumPreview: (mbid: string) => `/api/library/album/${mbid}/removal-preview`,
		removeAlbum: (mbid: string) => `/api/library/album/${mbid}`
	},
	search: {
		artists: (query: string) => `/api/search/artists?q=${encodeURIComponent(query)}`,
		albums: (query: string) => `/api/search/albums?q=${encodeURIComponent(query)}`,
		suggest: (query: string, limit = 5) =>
			`/api/search/suggest?q=${encodeURIComponent(query.trim())}&limit=${limit}`
	},
	home: () => '/api/home',
	homeIntegrationStatus: () => '/api/home/integration-status',
	discover: () => '/api/discover',
	discoverRefresh: () => '/api/discover/refresh',
	discoverQueue: (source?: string) =>
		`/api/discover/queue${source ? `?source=${source}` : ''}`,
	discoverQueueStatus: (source?: string) =>
		`/api/discover/queue/status${source ? `?source=${source}` : ''}`,
	discoverQueueGenerate: () => '/api/discover/queue/generate',
	discoverQueueEnrich: (mbid: string) => `/api/discover/queue/enrich/${mbid}`,
	discoverQueueIgnore: () => '/api/discover/queue/ignore',
	discoverQueueIgnored: () => '/api/discover/queue/ignored',
	discoverQueueValidate: () => '/api/discover/queue/validate',
	discoverQueueYoutubeSearch: (artist: string, album: string) =>
		`/api/discover/queue/youtube-search?artist=${encodeURIComponent(artist)}&album=${encodeURIComponent(album)}`,
	discoverQueueYoutubeQuota: () => '/api/discover/queue/youtube-quota',
	youtube: {
		generate: () => '/api/youtube/generate',
		link: (albumId: string) => `/api/youtube/link/${albumId}`,
		links: () => '/api/youtube/links',
		deleteLink: (albumId: string) => `/api/youtube/link/${albumId}`,
		updateLink: (albumId: string) => `/api/youtube/link/${albumId}`,
		manual: () => '/api/youtube/manual',
		generateTrack: () => '/api/youtube/generate-track',
		generateTracks: () => '/api/youtube/generate-tracks',
		trackLinks: (albumId: string) => `/api/youtube/track-links/${albumId}`,
		deleteTrackLink: (albumId: string, trackNumber: number) =>
			`/api/youtube/track-link/${albumId}/${trackNumber}`,
		quota: () => '/api/youtube/quota'
	},
	queue: () => '/api/queue',
	settings: () => '/api/settings',
	settingsLocalFiles: () => '/api/settings/local-files',
	settingsLocalFilesVerify: () => '/api/settings/local-files/verify',
	stream: {
		jellyfin: (itemId: string, format = 'aac', bitrate = 128000) =>
			`/api/stream/jellyfin/${itemId}?format=${format}&bitrate=${bitrate}`,
		jellyfinStart: (itemId: string) => `/api/stream/jellyfin/${itemId}/start`,
		jellyfinProgress: (itemId: string) => `/api/stream/jellyfin/${itemId}/progress`,
		jellyfinStop: (itemId: string) => `/api/stream/jellyfin/${itemId}/stop`,
		local: (trackId: number | string) => `/api/stream/local/${trackId}`
	},
	jellyfinLibrary: {
		albumMatch: (mbid: string) => `/api/jellyfin/albums/match/${mbid}`,
		albums: (
			limit = 50,
			offset = 0,
			sortBy = 'SortName',
			genre?: string,
			sortOrder = 'Ascending'
		) => {
			let url = `/api/jellyfin/albums?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (genre) url += `&genre=${encodeURIComponent(genre)}`;
			return url;
		},
		albumDetail: (id: string) => `/api/jellyfin/albums/${id}`,
		albumTracks: (id: string) => `/api/jellyfin/albums/${id}/tracks`,
		search: (query: string) => `/api/jellyfin/search?q=${encodeURIComponent(query)}`,
		artists: (limit = 50, offset = 0) => `/api/jellyfin/artists?limit=${limit}&offset=${offset}`,
		recent: () => '/api/jellyfin/recent',
		favorites: () => '/api/jellyfin/favorites',
		genres: () => '/api/jellyfin/genres',
		stats: () => '/api/jellyfin/stats'
	},
	local: {
		albumMatch: (mbid: string) => `/api/local/albums/match/${mbid}`,
		albums: (limit = 50, offset = 0, sortBy = 'name', q?: string, sortOrder = 'asc') => {
			let url = `/api/local/albums?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (q) url += `&q=${encodeURIComponent(q)}`;
			return url;
		},
		albumTracks: (id: number | string) => `/api/local/albums/${id}/tracks`,
		search: (query: string) => `/api/local/search?q=${encodeURIComponent(query)}`,
		recent: () => '/api/local/recent',
		stats: () => '/api/local/stats'
	}
} as const;

export const MESSAGES = {
	ERRORS: {
		LOAD_ALBUM: 'Failed to load album',
		LOAD_ARTIST: 'Failed to load artist',
		LOAD_TRACKS: 'Failed to load tracks',
		LOAD_RELEASES: 'Failed to load releases',
		NETWORK: 'Network error occurred',
		NOT_FOUND: 'Resource not found',
		REQUEST_FAILED: 'Request failed'
	},
	SUCCESS: {
		ADDED_TO_LIBRARY: 'Added to Library',
		REQUESTED: 'Request submitted successfully'
	}
} as const;
