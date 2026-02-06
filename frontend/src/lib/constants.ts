export const CACHE_KEYS = {
	LIBRARY_MBIDS: 'musicseerr_library_mbids',
	RECENTLY_ADDED: 'musicseerr_recently_added',
	HOME_CACHE: 'musicseerr_home_cache',
	DISCOVER_CACHE: 'musicseerr_discover_cache',
	DISCOVER_QUEUE: 'musicseerr_discover_queue'
} as const;

export const CACHE_TTL = {
	DEFAULT: 5 * 60 * 1000,
	LIBRARY: 5 * 60 * 1000,
	RECENTLY_ADDED: 5 * 60 * 1000,
	HOME: 5 * 60 * 1000,
	DISCOVER: 30 * 60 * 1000,
	DISCOVER_QUEUE: 24 * 60 * 60 * 1000
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
		artists: () => '/api/library/artists'
	},
	search: {
		artists: (query: string) => `/api/search/artists?query=${encodeURIComponent(query)}`,
		albums: (query: string) => `/api/search/albums?query=${encodeURIComponent(query)}`
	},
	home: () => '/api/home',
	discover: () => '/api/discover',
	discoverRefresh: () => '/api/discover/refresh',
	discoverQueue: () => '/api/discover/queue',
	discoverQueueEnrich: (mbid: string) => `/api/discover/queue/enrich/${mbid}`,
	discoverQueueIgnore: () => '/api/discover/queue/ignore',
	discoverQueueIgnored: () => '/api/discover/queue/ignored',
	discoverQueueValidate: () => '/api/discover/queue/validate',
	discoverQueueYoutubeSearch: (artist: string, album: string) =>
		`/api/discover/queue/youtube-search?artist=${encodeURIComponent(artist)}&album=${encodeURIComponent(album)}`,
	queue: () => '/api/queue',
	settings: () => '/api/settings'
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
