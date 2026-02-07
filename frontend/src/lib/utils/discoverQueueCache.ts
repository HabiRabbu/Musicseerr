import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';
import type { DiscoverQueueItemFull } from '$lib/types';

export interface QueueCacheData {
	items: DiscoverQueueItemFull[];
	currentIndex: number;
	queueId: string;
}

const queueCache = createLocalStorageCache<QueueCacheData>(
	CACHE_KEYS.DISCOVER_QUEUE,
	CACHE_TTL.DISCOVER_QUEUE
);

export const getQueueCachedData = queueCache.get;
export const setQueueCachedData = queueCache.set;
export const isQueueCacheStale = queueCache.isStale;
export const updateDiscoverQueueCacheTTL = queueCache.updateTTL;
