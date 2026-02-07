import { browser } from '$app/environment';
import { CACHE_TTL } from '$lib/constants';
import { updateHomeCacheTTL } from '$lib/utils/homeCache';
import { updateDiscoverCacheTTL } from '$lib/utils/discoverCache';
import { updateDiscoveryCacheTTL } from '$lib/stores/discoveryCache';
import { updateDiscoverQueueCacheTTL } from '$lib/utils/discoverQueueCache';
import { updateSearchCacheTTL } from '$lib/stores/search';
import { libraryStore } from '$lib/stores/library';
import { recentlyAddedStore } from '$lib/stores/recentlyAdded';

export interface CacheTTLs {
	home: number;
	discover: number;
	library: number;
	recentlyAdded: number;
	discoverQueue: number;
	search: number;
}

const DEFAULTS: CacheTTLs = {
	home: CACHE_TTL.HOME,
	discover: CACHE_TTL.DISCOVER,
	library: CACHE_TTL.LIBRARY,
	recentlyAdded: CACHE_TTL.RECENTLY_ADDED,
	discoverQueue: CACHE_TTL.DISCOVER_QUEUE,
	search: CACHE_TTL.SEARCH
};

let resolved: CacheTTLs = { ...DEFAULTS };
let initialized = false;

function applyTTLs(ttls: CacheTTLs): void {
	updateHomeCacheTTL(ttls.home);
	updateDiscoverCacheTTL(ttls.discover);
	libraryStore.updateCacheTTL(ttls.library);
	recentlyAddedStore.updateCacheTTL(ttls.recentlyAdded);
	updateDiscoveryCacheTTL(ttls.discover);
	updateDiscoverQueueCacheTTL(ttls.discoverQueue);
	updateSearchCacheTTL(ttls.search);
}

export async function initCacheTTLs(): Promise<void> {
	if (!browser || initialized) return;
	initialized = true;

	try {
		const res = await fetch('/api/settings/cache-ttls');
		if (res.ok) {
			const data = await res.json();
			resolved = {
				home: data.home ?? DEFAULTS.home,
				discover: data.discover ?? DEFAULTS.discover,
				library: data.library ?? DEFAULTS.library,
				recentlyAdded: data.recently_added ?? DEFAULTS.recentlyAdded,
				discoverQueue: data.discover_queue ?? DEFAULTS.discoverQueue,
				search: data.search ?? DEFAULTS.search
			};
			applyTTLs(resolved);
		}
	} catch (e) {
		console.warn('[cacheTtl] Failed to load cache TTL settings, using defaults', e);
	}
}

export function getCacheTTLs(): CacheTTLs {
	return resolved;
}

export function getCacheTTL(key: keyof CacheTTLs): number {
	return resolved[key];
}
