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

const QUEUE_CACHE_EVENT = 'discover-queue-cache-changed';

function notifyQueueCacheChanged(source?: string): void {
	if (typeof window === 'undefined') return;
	window.dispatchEvent(
		new CustomEvent<{ source?: string }>(QUEUE_CACHE_EVENT, {
			detail: { source }
		})
	);
}

export function subscribeQueueCacheChanges(listener: (source?: string) => void): () => void {
	if (typeof window === 'undefined') return () => {};

	const handler = (event: Event) => {
		const customEvent = event as CustomEvent<{ source?: string }>;
		listener(customEvent.detail?.source);
	};

	window.addEventListener(QUEUE_CACHE_EVENT, handler);
	return () => {
		window.removeEventListener(QUEUE_CACHE_EVENT, handler);
	};
}

export const getQueueCachedData = (source?: string) => {
	const cached = queueCache.get(source);
	if (!cached) return null;

	if (queueCache.isStale(cached.timestamp)) {
		queueCache.remove(source);
		notifyQueueCacheChanged(source);
		return null;
	}

	return cached;
};

export const setQueueCachedData = (data: QueueCacheData, source?: string) => {
	queueCache.set(data, source);
	notifyQueueCacheChanged(source);
};

export const removeQueueCachedData = (source?: string) => {
	queueCache.remove(source);
	notifyQueueCacheChanged(source);
};
export const isQueueCacheStale = queueCache.isStale;
export const updateDiscoverQueueCacheTTL = queueCache.updateTTL;

const KNOWN_SOURCES = ['listenbrainz', 'lastfm'] as const;

export function removeAllQueueCachedData(): void {
	removeQueueCachedData();
	for (const src of KNOWN_SOURCES) {
		removeQueueCachedData(src);
	}
}
