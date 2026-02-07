import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';
import type { HomeResponse } from '$lib/types';

const homeCache = createLocalStorageCache<HomeResponse>(CACHE_KEYS.HOME_CACHE, CACHE_TTL.HOME);

export const getHomeCachedData = homeCache.get;
export const setHomeCachedData = homeCache.set;
export const isHomeCacheStale = homeCache.isStale;
export const updateHomeCacheTTL = homeCache.updateTTL;

export { formatLastUpdated } from '$lib/utils/formatting';

export function getGreeting(): string {
	const hour = new Date().getHours();
	if (hour < 12) return 'Good morning';
	if (hour < 18) return 'Good afternoon';
	return 'Good evening';
}
