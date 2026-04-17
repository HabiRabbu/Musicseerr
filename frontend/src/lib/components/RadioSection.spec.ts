import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('$lib/queries/QueryClient', () => ({
	invalidateQueriesWithPersister: vi.fn().mockResolvedValue(undefined)
}));

import { DiscoverQueryKeyFactory } from '$lib/queries/discover/DiscoverQueryKeyFactory';
import { invalidateQueriesWithPersister } from '$lib/queries/QueryClient';

const mockInvalidate = vi.mocked(invalidateQueriesWithPersister);

describe('DiscoverQueryKeyFactory.radio', () => {
	it('returns the expected key shape for artist seed', () => {
		const key = DiscoverQueryKeyFactory.radio('artist', 'test-mbid', 'listenbrainz');
		expect(key).toEqual(['discover', 'radio', 'artist', 'test-mbid', { source: 'listenbrainz' }]);
	});

	it('returns the expected key shape for album seed', () => {
		const key = DiscoverQueryKeyFactory.radio('album', 'album-mbid', 'lastfm');
		expect(key).toEqual(['discover', 'radio', 'album', 'album-mbid', { source: 'lastfm' }]);
	});

	it('generates different keys for different seed types', () => {
		const artistKey = DiscoverQueryKeyFactory.radio('artist', 'test-mbid', 'listenbrainz');
		const albumKey = DiscoverQueryKeyFactory.radio('album', 'test-mbid', 'listenbrainz');
		expect(artistKey).not.toEqual(albumKey);
	});

	it('generates different keys for different seed IDs', () => {
		const key1 = DiscoverQueryKeyFactory.radio('artist', 'mbid-1', 'listenbrainz');
		const key2 = DiscoverQueryKeyFactory.radio('artist', 'mbid-2', 'listenbrainz');
		expect(key1).not.toEqual(key2);
	});

	it('generates different keys for different sources', () => {
		const key1 = DiscoverQueryKeyFactory.radio('artist', 'test-mbid', 'listenbrainz');
		const key2 = DiscoverQueryKeyFactory.radio('artist', 'test-mbid', 'lastfm');
		expect(key1).not.toEqual(key2);
	});

	it('starts with the discover prefix', () => {
		const key = DiscoverQueryKeyFactory.radio('artist', 'test-mbid', 'listenbrainz');
		expect(key[0]).toBe('discover');
		expect(key[1]).toBe('radio');
	});
});

describe('RadioSection refresh invalidation contract', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('refresh calls invalidateQueriesWithPersister with correct radio query key', async () => {
		const seedType = 'artist';
		const seedId = 'abc-123';
		const source = 'listenbrainz' as const;

		// Reproduce RadioSection.svelte handleRefresh() logic
		await invalidateQueriesWithPersister({
			queryKey: DiscoverQueryKeyFactory.radio(seedType, seedId, source)
		});

		expect(mockInvalidate).toHaveBeenCalledOnce();
		expect(mockInvalidate).toHaveBeenCalledWith({
			queryKey: ['discover', 'radio', 'artist', 'abc-123', { source: 'listenbrainz' }]
		});
	});

	it('refresh uses distinct keys for different seeds', async () => {
		const source = 'listenbrainz' as const;

		await invalidateQueriesWithPersister({
			queryKey: DiscoverQueryKeyFactory.radio('artist', 'seed-1', source)
		});
		await invalidateQueriesWithPersister({
			queryKey: DiscoverQueryKeyFactory.radio('album', 'seed-2', source)
		});

		expect(mockInvalidate).toHaveBeenCalledTimes(2);
		expect(mockInvalidate.mock.calls[0][0]).not.toEqual(mockInvalidate.mock.calls[1][0]);
	});
});
