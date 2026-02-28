type CachedEntry<T> = {
	data: T;
	timestamp: number;
};

type LocalStorageDetailCache<T> = {
	get: (suffix?: string) => CachedEntry<T> | null;
	isStale: (timestamp: number) => boolean;
};

type HydrateCacheEntryParams<T> = {
	cache: LocalStorageDetailCache<T>;
	cacheKey: string;
	onHydrate: (data: T) => void;
};

export function hydrateDetailCacheEntry<T>({
	cache,
	cacheKey,
	onHydrate
}: HydrateCacheEntryParams<T>): boolean {
	const cachedEntry = cache.get(cacheKey);
	if (!cachedEntry) {
		return true;
	}

	onHydrate(cachedEntry.data);
	return cache.isStale(cachedEntry.timestamp);
}
