import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';
import type { DiscoverResponse } from '$lib/types';

const discoverCache = createLocalStorageCache<DiscoverResponse>(
	CACHE_KEYS.DISCOVER_CACHE,
	CACHE_TTL.DISCOVER
);

export const getDiscoverCachedData = discoverCache.get;
export const setDiscoverCachedData = discoverCache.set;
export const isDiscoverCacheStale = discoverCache.isStale;
export const updateDiscoverCacheTTL = discoverCache.updateTTL;
