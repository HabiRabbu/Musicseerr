import { browser } from '$app/environment';
import { CACHE_TTL } from '$lib/constants';
import { updateHomeCacheTTL } from '$lib/utils/homeCache';
import { updateDiscoverCacheTTL } from '$lib/utils/discoverCache';
import { updateDiscoveryCacheTTL } from '$lib/stores/discoveryCache';
import { updateDiscoverQueueCacheTTL } from '$lib/utils/discoverQueueCache';
import { updateSearchCacheTTL } from '$lib/stores/search';
import { updateJellyfinSidebarCacheTTL } from '$lib/utils/jellyfinLibraryCache';
import { updateLocalFilesSidebarCacheTTL } from '$lib/utils/localFilesCache';
import { libraryStore } from '$lib/stores/library';
import { recentlyAddedStore } from '$lib/stores/recentlyAdded';

export interface CacheTTLs {
	home: number;
	discover: number;
	library: number;
	recentlyAdded: number;
	discoverQueue: number;
	search: number;
	localFilesSidebar: number;
	jellyfinSidebar: number;
	discoverQueuePollingInterval: number;
	discoverQueueAutoGenerate: boolean;
}

const DEFAULTS: CacheTTLs = {
	home: CACHE_TTL.HOME,
	discover: CACHE_TTL.DISCOVER,
	library: CACHE_TTL.LIBRARY,
	recentlyAdded: CACHE_TTL.RECENTLY_ADDED,
	discoverQueue: CACHE_TTL.DISCOVER_QUEUE,
	search: CACHE_TTL.SEARCH,
	localFilesSidebar: CACHE_TTL.LOCAL_FILES_SIDEBAR,
	jellyfinSidebar: CACHE_TTL.JELLYFIN_SIDEBAR,
	discoverQueuePollingInterval: 4000,
	discoverQueueAutoGenerate: true
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
	updateLocalFilesSidebarCacheTTL(ttls.localFilesSidebar);
	updateJellyfinSidebarCacheTTL(ttls.jellyfinSidebar);
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
				search: data.search ?? DEFAULTS.search,
				localFilesSidebar: data.local_files_sidebar ?? DEFAULTS.localFilesSidebar,
				jellyfinSidebar: data.jellyfin_sidebar ?? DEFAULTS.jellyfinSidebar,
				discoverQueuePollingInterval:
					data.discover_queue_polling_interval ?? DEFAULTS.discoverQueuePollingInterval,
				discoverQueueAutoGenerate:
					data.discover_queue_auto_generate ?? DEFAULTS.discoverQueueAutoGenerate
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

export function getCacheTTL<K extends keyof CacheTTLs>(key: K): CacheTTLs[K] {
	return resolved[key];
}
