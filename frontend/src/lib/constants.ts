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
		NAVIDROME_SIDEBAR: 'musicseerr_navidrome_sidebar',
		NAVIDROME_ALBUMS_LIST: 'musicseerr_navidrome_albums_list',
		LOCAL_FILES_ALBUMS_LIST: 'musicseerr_local_files_albums_list'
	},
	detail: {
		ALBUM_BASIC_CACHE: 'musicseerr_album_basic_cache',
		ALBUM_TRACKS_CACHE: 'musicseerr_album_tracks_cache',
		ALBUM_DISCOVERY_CACHE: 'musicseerr_album_discovery_cache',
		ALBUM_LASTFM_CACHE: 'musicseerr_album_lastfm_cache',
		ALBUM_YOUTUBE_CACHE: 'musicseerr_album_youtube_cache',
		ALBUM_SOURCE_MATCH_CACHE: 'musicseerr_album_source_match_cache',
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
		NAVIDROME_SIDEBAR: 2 * 60 * 1000,
		NAVIDROME_ALBUMS_LIST: 2 * 60 * 1000,
		LOCAL_FILES_ALBUMS_LIST: 2 * 60 * 1000,
		PLAYLIST_SOURCES: 15 * 60 * 1000
	},
	detail: {
		ALBUM_DETAIL_BASIC: 5 * 60 * 1000,
		ALBUM_DETAIL_TRACKS: 15 * 60 * 1000,
		ALBUM_DETAIL_DISCOVERY: 30 * 60 * 1000,
		ALBUM_DETAIL_LASTFM: 30 * 60 * 1000,
		ALBUM_DETAIL_YOUTUBE: 60 * 60 * 1000,
		ALBUM_DETAIL_SOURCE_MATCH: 5 * 60 * 1000,
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
		basic: (id: string) => `/api/v1/artists/${id}`,
		extended: (id: string) => `/api/v1/artists/${id}/extended`,
		releases: (id: string, offset: number, limit: number) =>
			`/api/v1/artists/${id}/releases?offset=${offset}&limit=${limit}`
	},
	album: {
		basic: (id: string) => `/api/v1/albums/${id}`,
		tracks: (id: string) => `/api/v1/albums/${id}/tracks`
	},
	library: {
		mbids: () => '/api/v1/library/mbids',
		albums: (limit = 50, offset = 0, sortBy = 'date_added', sortOrder = 'desc', q?: string) => {
			let url = `/api/v1/library/albums?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (q) url += `&q=${encodeURIComponent(q)}`;
			return url;
		},
		artists: (limit = 50, offset = 0, sortBy = 'name', sortOrder = 'asc', q?: string) => {
			let url = `/api/v1/library/artists?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (q) url += `&q=${encodeURIComponent(q)}`;
			return url;
		},
		removeAlbumPreview: (mbid: string) => `/api/v1/library/album/${mbid}/removal-preview`,
		removeAlbum: (mbid: string) => `/api/v1/library/album/${mbid}`,
		resolveTracks: () => '/api/v1/library/resolve-tracks'
	},
	search: {
		artists: (query: string) => `/api/v1/search/artists?q=${encodeURIComponent(query)}`,
		albums: (query: string) => `/api/v1/search/albums?q=${encodeURIComponent(query)}`,
		suggest: (query: string, limit = 5) =>
			`/api/v1/search/suggest?q=${encodeURIComponent(query.trim())}&limit=${limit}`
	},
	home: (source: string) => `/api/v1/home?source=${encodeURIComponent(source)}`,
	homeIntegrationStatus: () => '/api/v1/home/integration-status',
	discover: () => '/api/v1/discover',
	discoverRefresh: () => '/api/v1/discover/refresh',
	discoverQueue: (source?: string) => `/api/v1/discover/queue${source ? `?source=${source}` : ''}`,
	discoverQueueStatus: (source?: string) =>
		`/api/v1/discover/queue/status${source ? `?source=${source}` : ''}`,
	discoverQueueGenerate: () => '/api/v1/discover/queue/generate',
	discoverQueueEnrich: (mbid: string) => `/api/v1/discover/queue/enrich/${mbid}`,
	discoverQueueIgnore: () => '/api/v1/discover/queue/ignore',
	discoverQueueIgnored: () => '/api/v1/discover/queue/ignored',
	discoverQueueValidate: () => '/api/v1/discover/queue/validate',
	discoverQueueYoutubeSearch: (artist: string, album: string) =>
		`/api/v1/discover/queue/youtube-search?artist=${encodeURIComponent(artist)}&album=${encodeURIComponent(album)}`,
	discoverQueueYoutubeTrackSearch: (artist: string, track: string) =>
		`/api/v1/discover/queue/youtube-track-search?artist=${encodeURIComponent(artist)}&track=${encodeURIComponent(track)}`,
	discoverQueueYoutubeQuota: () => '/api/v1/discover/queue/youtube-quota',
	discoverQueueYoutubeCacheCheck: () => '/api/v1/discover/queue/youtube-cache-check',
	youtube: {
		generate: () => '/api/v1/youtube/generate',
		link: (albumId: string) => `/api/v1/youtube/link/${albumId}`,
		links: () => '/api/v1/youtube/links',
		deleteLink: (albumId: string) => `/api/v1/youtube/link/${albumId}`,
		updateLink: (albumId: string) => `/api/v1/youtube/link/${albumId}`,
		manual: () => '/api/v1/youtube/manual',
		generateTrack: () => '/api/v1/youtube/generate-track',
		generateTracks: () => '/api/v1/youtube/generate-tracks',
		trackLinks: (albumId: string) => `/api/v1/youtube/track-links/${albumId}`,
		deleteTrackLink: (albumId: string, discNumber: number, trackNumber: number) =>
			`/api/v1/youtube/track-link/${albumId}/${discNumber}/${trackNumber}`,
		quota: () => '/api/v1/youtube/quota'
	},
	queue: () => '/api/v1/queue',
	settings: () => '/api/v1/settings',
	settingsPrimarySource: () => '/api/v1/settings/primary-source',
	settingsNavidrome: () => '/api/v1/settings/navidrome',
	settingsNavidromeVerify: () => '/api/v1/settings/navidrome/verify',
	settingsLocalFiles: () => '/api/v1/settings/local-files',
	settingsLocalFilesVerify: () => '/api/v1/settings/local-files/verify',
	profile: {
		get: () => '/api/v1/profile',
		update: () => '/api/v1/profile',
		avatarUpload: () => '/api/v1/profile/avatar',
		avatar: () => '/api/v1/profile/avatar'
	},
	playlists: {
		list: () => '/api/v1/playlists',
		create: () => '/api/v1/playlists',
		detail: (id: string) => `/api/v1/playlists/${id}`,
		update: (id: string) => `/api/v1/playlists/${id}`,
		delete: (id: string) => `/api/v1/playlists/${id}`,
		addTracks: (id: string) => `/api/v1/playlists/${id}/tracks`,
		removeTracks: (id: string) => `/api/v1/playlists/${id}/tracks/remove`,
		removeTrack: (id: string, trackId: string) => `/api/v1/playlists/${id}/tracks/${trackId}`,
		updateTrack: (id: string, trackId: string) => `/api/v1/playlists/${id}/tracks/${trackId}`,
		reorderTrack: (id: string) => `/api/v1/playlists/${id}/tracks/reorder`,
		uploadCover: (id: string) => `/api/v1/playlists/${id}/cover`,
		getCover: (id: string) => `/api/v1/playlists/${id}/cover`,
		deleteCover: (id: string) => `/api/v1/playlists/${id}/cover`,
		checkTracks: () => '/api/v1/playlists/check-tracks',
		resolveSources: (id: string) => `/api/v1/playlists/${id}/resolve-sources`
	},
	stream: {
		jellyfin: (itemId: string) => `/api/v1/stream/jellyfin/${itemId}`,
		jellyfinStart: (itemId: string) => `/api/v1/stream/jellyfin/${itemId}/start`,
		jellyfinProgress: (itemId: string) => `/api/v1/stream/jellyfin/${itemId}/progress`,
		jellyfinStop: (itemId: string) => `/api/v1/stream/jellyfin/${itemId}/stop`,
		navidrome: (id: string) => `/api/v1/stream/navidrome/${id}`,
		navidromeScrobble: (id: string) => `/api/v1/stream/navidrome/${id}/scrobble`,
		navidromeNowPlaying: (id: string) => `/api/v1/stream/navidrome/${id}/now-playing`,
		local: (trackId: number | string) => `/api/v1/stream/local/${trackId}`
	},
	jellyfinLibrary: {
		albumMatch: (mbid: string) => `/api/v1/jellyfin/albums/match/${mbid}`,
		albums: (
			limit = 50,
			offset = 0,
			sortBy = 'SortName',
			genre?: string,
			sortOrder = 'Ascending'
		) => {
			let url = `/api/v1/jellyfin/albums?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (genre) url += `&genre=${encodeURIComponent(genre)}`;
			return url;
		},
		albumDetail: (id: string) => `/api/v1/jellyfin/albums/${id}`,
		albumTracks: (id: string) => `/api/v1/jellyfin/albums/${id}/tracks`,
		search: (query: string) => `/api/v1/jellyfin/search?q=${encodeURIComponent(query)}`,
		artists: (limit = 50, offset = 0) => `/api/v1/jellyfin/artists?limit=${limit}&offset=${offset}`,
		recent: () => '/api/v1/jellyfin/recent',
		favorites: () => '/api/v1/jellyfin/favorites',
		genres: () => '/api/v1/jellyfin/genres',
		stats: () => '/api/v1/jellyfin/stats'
	},
	navidromeLibrary: {
		albums: () => '/api/v1/navidrome/albums',
		albumDetail: (id: string) => `/api/v1/navidrome/albums/${id}`,
		artists: () => '/api/v1/navidrome/artists',
		artistDetail: (id: string) => `/api/v1/navidrome/artists/${id}`,
		search: (q: string) => `/api/v1/navidrome/search?q=${encodeURIComponent(q)}`,
		recent: () => '/api/v1/navidrome/recent',
		favorites: () => '/api/v1/navidrome/favorites',
		genres: () => '/api/v1/navidrome/genres',
		stats: () => '/api/v1/navidrome/stats',
		albumMatch: (albumId: string) => `/api/v1/navidrome/album-match/${albumId}`
	},
	local: {
		albumMatch: (mbid: string) => `/api/v1/local/albums/match/${mbid}`,
		albums: (limit = 50, offset = 0, sortBy = 'name', q?: string, sortOrder = 'asc') => {
			let url = `/api/v1/local/albums?limit=${limit}&offset=${offset}&sort_by=${sortBy}&sort_order=${sortOrder}`;
			if (q) url += `&q=${encodeURIComponent(q)}`;
			return url;
		},
		albumTracks: (id: number | string) => `/api/v1/local/albums/${id}/tracks`,
		search: (query: string) => `/api/v1/local/search?q=${encodeURIComponent(query)}`,
		recent: () => '/api/v1/local/recent',
		stats: () => '/api/v1/local/stats'
	}
} as const;

export const MESSAGES = {
	ERRORS: {
		LOAD_ALBUM: 'Failed to load album',
		LOAD_ARTIST: 'Failed to load artist',
		LOAD_TRACKS: "Couldn't load the track list",
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
