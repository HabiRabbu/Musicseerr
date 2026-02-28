import { describe, expect, it, vi } from 'vitest';
import { hydrateDetailCacheEntry } from './detailCacheHydration';

describe('hydrateDetailCacheEntry', () => {
	it('hydrates data and returns stale status when cache exists', () => {
		const onHydrate = vi.fn();
		const cache = {
			get: vi.fn().mockReturnValue({ data: { value: 42 }, timestamp: 1234 }),
			isStale: vi.fn().mockReturnValue(false)
		};

		const shouldRefresh = hydrateDetailCacheEntry({
			cache,
			cacheKey: 'album-id',
			onHydrate
		});

		expect(cache.get).toHaveBeenCalledWith('album-id');
		expect(onHydrate).toHaveBeenCalledWith({ value: 42 });
		expect(cache.isStale).toHaveBeenCalledWith(1234);
		expect(shouldRefresh).toBe(false);
	});

	it('returns refresh=true when cache entry is missing', () => {
		const onHydrate = vi.fn();
		const cache = {
			get: vi.fn().mockReturnValue(null),
			isStale: vi.fn()
		};

		const shouldRefresh = hydrateDetailCacheEntry({
			cache,
			cacheKey: 'artist-id',
			onHydrate
		});

		expect(cache.get).toHaveBeenCalledWith('artist-id');
		expect(onHydrate).not.toHaveBeenCalled();
		expect(cache.isStale).not.toHaveBeenCalled();
		expect(shouldRefresh).toBe(true);
	});
});
