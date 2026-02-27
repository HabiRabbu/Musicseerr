import { describe, it, expect } from 'vitest';
import { getTimeRangeFallbackPath } from './timeRangeFallback';
import type { HomeAlbum, HomeArtist } from '$lib/types';

describe('getTimeRangeFallbackPath', () => {
	it('returns album search path for no-MBID album items', () => {
		expect.assertions(1);
		const item: HomeAlbum = {
			mbid: null,
			name: 'Kid A',
			artist_name: 'Radiohead',
			artist_mbid: null,
			image_url: null,
			release_date: null,
			listen_count: null,
			in_library: false
		};
		expect(getTimeRangeFallbackPath('album', item)).toBe('/search/albums?q=Radiohead%20Kid%20A');
	});

	it('returns artist search path for no-MBID artist items', () => {
		expect.assertions(1);
		const item: HomeArtist = {
			mbid: null,
			name: 'Massive Attack',
			image_url: null,
			listen_count: null,
			in_library: false
		};
		expect(getTimeRangeFallbackPath('artist', item)).toBe('/search/artists?q=Massive%20Attack');
	});

	it('returns null for empty artist names', () => {
		expect.assertions(1);
		const item: HomeArtist = {
			mbid: null,
			name: '   ',
			image_url: null,
			listen_count: null,
			in_library: false
		};
		expect(getTimeRangeFallbackPath('artist', item)).toBeNull();
	});
});
