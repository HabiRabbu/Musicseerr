import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import type { JellyfinAlbumSummary, JellyfinLibraryStats } from '$lib/types';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';

type JellyfinSidebarData = {
	recentAlbums: JellyfinAlbumSummary[];
	favoriteAlbums: JellyfinAlbumSummary[];
	genres: string[];
	stats: JellyfinLibraryStats | null;
};

const jellyfinSidebarCache = createLocalStorageCache<JellyfinSidebarData>(
	CACHE_KEYS.JELLYFIN_SIDEBAR,
	CACHE_TTL.JELLYFIN_SIDEBAR
);

export const getJellyfinSidebarCachedData = jellyfinSidebarCache.get;
export const setJellyfinSidebarCachedData = jellyfinSidebarCache.set;
export const isJellyfinSidebarCacheStale = jellyfinSidebarCache.isStale;
export const updateJellyfinSidebarCacheTTL = jellyfinSidebarCache.updateTTL;
