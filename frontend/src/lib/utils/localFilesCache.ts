import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import type { LocalAlbumSummary, LocalStorageStats } from '$lib/types';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';

type LocalFilesSidebarData = {
	recentAlbums: LocalAlbumSummary[];
	stats: LocalStorageStats | null;
};

type LocalFilesAlbumsListData = {
	items: LocalAlbumSummary[];
	total: number;
};

export const localFilesSidebarCache = createLocalStorageCache<LocalFilesSidebarData>(
	CACHE_KEYS.LOCAL_FILES_SIDEBAR,
	CACHE_TTL.LOCAL_FILES_SIDEBAR
);

export const localFilesAlbumsListCache = createLocalStorageCache<LocalFilesAlbumsListData>(
	CACHE_KEYS.LOCAL_FILES_ALBUMS_LIST,
	CACHE_TTL.LOCAL_FILES_ALBUMS_LIST,
	{ maxEntries: 80 }
);

export const getLocalFilesSidebarCachedData = localFilesSidebarCache.get;
export const setLocalFilesSidebarCachedData = localFilesSidebarCache.set;
export const isLocalFilesSidebarCacheStale = localFilesSidebarCache.isStale;
export const updateLocalFilesSidebarCacheTTL = localFilesSidebarCache.updateTTL;

export const getLocalFilesAlbumsListCachedData = localFilesAlbumsListCache.get;
export const setLocalFilesAlbumsListCachedData = localFilesAlbumsListCache.set;
export const isLocalFilesAlbumsListCacheStale = localFilesAlbumsListCache.isStale;
export const updateLocalFilesAlbumsListCacheTTL = localFilesAlbumsListCache.updateTTL;
