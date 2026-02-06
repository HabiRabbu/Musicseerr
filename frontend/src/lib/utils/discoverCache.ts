import { browser } from '$app/environment';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import type { DiscoverResponse } from '$lib/types';

interface CachedDiscoverData {
	data: DiscoverResponse;
	timestamp: number;
}

export function getDiscoverCachedData(): CachedDiscoverData | null {
	if (!browser) return null;
	try {
		const cached = localStorage.getItem(CACHE_KEYS.DISCOVER_CACHE);
		if (cached) {
			const parsed: CachedDiscoverData = JSON.parse(cached);
			if (isDiscoverCacheStale(parsed.timestamp)) {
				localStorage.removeItem(CACHE_KEYS.DISCOVER_CACHE);
				return null;
			}
			return parsed;
		}
	} catch {}
	return null;
}

export function setDiscoverCachedData(data: DiscoverResponse): void {
	if (!browser) return;
	try {
		const cacheEntry: CachedDiscoverData = {
			data,
			timestamp: Date.now()
		};
		localStorage.setItem(CACHE_KEYS.DISCOVER_CACHE, JSON.stringify(cacheEntry));
	} catch {}
}

export function isDiscoverCacheStale(timestamp: number): boolean {
	return Date.now() - timestamp > CACHE_TTL.DISCOVER;
}
