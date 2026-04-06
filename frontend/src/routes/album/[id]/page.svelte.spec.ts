import { page } from '@vitest/browser/context';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render } from 'vitest-browser-svelte';

const {
	mockGoto,
	mockPageFetch,
	mockHydrateDetailCacheEntry,
	mockAlbumBasicCache,
	mockAlbumTracksCache,
	mockAlbumDiscoveryCache,
	mockAlbumLastFmCache,
	mockAlbumYouTubeCache,
	mockAlbumSourceMatchCache
} = vi.hoisted(() => ({
	mockGoto: vi.fn(),
	mockPageFetch: vi.fn(),
	mockHydrateDetailCacheEntry: vi.fn(),
	mockAlbumBasicCache: { set: vi.fn() },
	mockAlbumTracksCache: { set: vi.fn() },
	mockAlbumDiscoveryCache: { set: vi.fn() },
	mockAlbumLastFmCache: { set: vi.fn() },
	mockAlbumYouTubeCache: { get: vi.fn(), set: vi.fn() },
	mockAlbumSourceMatchCache: { get: vi.fn(), set: vi.fn() }
}));

vi.mock('$app/environment', () => ({ browser: true }));
vi.mock('$app/navigation', () => ({
	goto: (...args: unknown[]) => mockGoto(...args)
}));

vi.mock('$lib/stores/library', () => ({
	libraryStore: {
		isInLibrary: vi.fn(() => false),
		isRequested: vi.fn(() => false)
	}
}));

const integrationState = {
	youtube: false,
	youtube_api: false,
	jellyfin: false,
	localfiles: true,
	navidrome: true,
	lastfm: false,
	lidarr: true
};

vi.mock('$lib/stores/integration', () => ({
	integrationStore: {
		subscribe: vi.fn((cb: (value: unknown) => void) => {
			cb(integrationState);
			return () => {};
		}),
		ensureLoaded: vi.fn().mockResolvedValue(undefined)
	}
}));

vi.mock('$lib/stores/player.svelte', () => ({
	playerStore: {
		isPlaying: false,
		nowPlaying: null,
		currentQueueItem: null,
		addToQueue: vi.fn(),
		playNext: vi.fn(),
		playMultipleNext: vi.fn(),
		addMultipleToQueue: vi.fn()
	}
}));

vi.mock('$lib/utils/navigationAbort', () => ({
	pageFetch: (...args: unknown[]) => mockPageFetch(...args)
}));

vi.mock('$lib/utils/detailCacheHydration', () => ({
	hydrateDetailCacheEntry: (...args: unknown[]) => mockHydrateDetailCacheEntry(...args)
}));

vi.mock('$lib/utils/albumDetailCache', () => ({
	albumBasicCache: mockAlbumBasicCache,
	albumTracksCache: mockAlbumTracksCache,
	albumDiscoveryCache: mockAlbumDiscoveryCache,
	albumLastFmCache: mockAlbumLastFmCache,
	albumYouTubeCache: mockAlbumYouTubeCache,
	albumSourceMatchCache: mockAlbumSourceMatchCache
}));

vi.mock('$lib/utils/serviceStatus', () => ({
	extractServiceStatus: vi.fn()
}));

vi.mock('$lib/utils/albumRequest', () => ({
	requestAlbum: vi.fn().mockResolvedValue({ success: true })
}));

vi.mock('$lib/components/AlbumImage.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/Toast.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/DiscoveryAlbumCarousel.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/LastFmAlbumEnrichment.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/ContextMenu.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/AddToPlaylistModal.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/BackButton.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/TrackPlayButton.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/JellyfinIcon.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/LocalFilesIcon.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/NavidromeIcon.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/DeleteAlbumModal.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/ArtistRemovedModal.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});
vi.mock('$lib/components/NowPlayingIndicator.svelte', () => {
	const Comp = function () {};
	Comp.prototype = {};
	return { default: Comp };
});

vi.mock('$lib/player/launchJellyfinPlayback', () => ({ launchJellyfinPlayback: vi.fn() }));
vi.mock('$lib/player/launchLocalPlayback', () => ({ launchLocalPlayback: vi.fn() }));
vi.mock('$lib/player/launchNavidromePlayback', () => ({ launchNavidromePlayback: vi.fn() }));

import AlbumPage from './+page.svelte';

const albumId = '3f3a6d95-326e-4384-80b0-0744f20f24ff';

function jsonResponse(payload: unknown, status = 200): Response {
	return new Response(JSON.stringify(payload), {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

describe('album detail page track rendering', () => {
	beforeEach(() => {
		mockGoto.mockReset();
		mockPageFetch.mockReset();
		mockHydrateDetailCacheEntry.mockReset();
		// eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock with generic cache type
		mockHydrateDetailCacheEntry.mockImplementation(({ cache, onHydrate }: any) => {
			if (cache === mockAlbumBasicCache) {
				onHydrate({
					title: 'Visions',
					musicbrainz_id: albumId,
					artist_name: 'Grimes',
					artist_id: 'artist-1',
					in_library: true,
					requested: false,
					cover_url: null
				});
				return false;
			}

			if (cache === mockAlbumTracksCache) {
				onHydrate({
					tracks: [
						{
							position: 1,
							disc_number: 1,
							title: 'Infinite ❤️ Without Fulfillment',
							length: 95327
						},
						{ position: 5, disc_number: 1, title: 'Circumambient', length: 223280 },
						{ position: 1, disc_number: 2, title: 'Ambrosia', length: 213093 },
						{ position: 5, disc_number: 2, title: 'Be a Body (Baarsden rework)', length: 204626 }
					],
					total_tracks: 4,
					total_length: 736326,
					label: null,
					barcode: null,
					country: null
				});
				return false;
			}

			if (cache === mockAlbumDiscoveryCache) {
				return true;
			}

			if (cache === mockAlbumLastFmCache) {
				return true;
			}

			return true;
		});
		mockPageFetch.mockImplementation((input: string | URL) => {
			const url = typeof input === 'string' ? input : input.toString();

			if (url.endsWith(`/api/v1/albums/${albumId}/basic`)) {
				return Promise.resolve(
					jsonResponse({
						title: 'Visions',
						musicbrainz_id: albumId,
						artist_name: 'Grimes',
						artist_id: 'artist-1',
						in_library: true,
						requested: false,
						cover_url: null
					})
				);
			}

			if (url.endsWith(`/api/v1/albums/${albumId}/tracks`)) {
				return Promise.resolve(
					jsonResponse({
						tracks: [
							{
								position: 1,
								disc_number: 1,
								title: 'Infinite ❤️ Without Fulfillment',
								length: 95327
							},
							{ position: 5, disc_number: 1, title: 'Circumambient', length: 223280 },
							{ position: 1, disc_number: 2, title: 'Ambrosia', length: 213093 },
							{ position: 5, disc_number: 2, title: 'Be a Body (Baarsden rework)', length: 204626 }
						],
						total_tracks: 4,
						total_length: 736326,
						label: null,
						barcode: null,
						country: null
					})
				);
			}

			if (url.includes(`/api/v1/albums/${albumId}/more-by-artist`)) {
				return Promise.resolve(jsonResponse({ artist_name: 'Grimes', albums: [] }));
			}

			if (url.includes(`/api/v1/albums/${albumId}/similar`)) {
				return Promise.resolve(jsonResponse({ albums: [] }));
			}

			if (url.endsWith(`/api/v1/youtube/link/${albumId}`)) {
				return Promise.resolve(jsonResponse({ detail: 'not found' }, 404));
			}

			if (url.endsWith(`/api/v1/youtube/track-links/${albumId}`)) {
				return Promise.resolve(jsonResponse([]));
			}

			if (url.endsWith(`/api/v1/jellyfin/albums/match/${albumId}`)) {
				return Promise.resolve(jsonResponse({ found: false, jellyfin_album_id: null, tracks: [] }));
			}

			if (url.endsWith(`/api/v1/local/albums/match/${albumId}`)) {
				return Promise.resolve(
					jsonResponse({
						found: true,
						tracks: [
							{
								track_file_id: 1,
								title: 'Infinite ❤️ Without Fulfillment',
								track_number: 1,
								disc_number: 1,
								duration_seconds: 95,
								size_bytes: 1,
								format: 'flac'
							},
							{
								track_file_id: 2,
								title: 'Circumambient',
								track_number: 5,
								disc_number: 1,
								duration_seconds: 223,
								size_bytes: 1,
								format: 'flac'
							},
							{
								track_file_id: 3,
								title: 'Ambrosia',
								track_number: 1,
								disc_number: 2,
								duration_seconds: 213,
								size_bytes: 1,
								format: 'flac'
							},
							{
								track_file_id: 4,
								title: 'Be a Body (Baarsden rework)',
								track_number: 5,
								disc_number: 2,
								duration_seconds: 204,
								size_bytes: 1,
								format: 'flac'
							}
						],
						total_size_bytes: 4,
						primary_format: 'flac'
					})
				);
			}

			if (url.includes(`/api/v1/navidrome/album-match/${albumId}`)) {
				return Promise.resolve(
					jsonResponse({
						found: true,
						navidrome_album_id: 'nav-1',
						tracks: [
							{
								navidrome_id: 'n1',
								title: 'Infinite ❤️ Without Fulfillment',
								track_number: 1,
								disc_number: 1,
								duration_seconds: 95,
								codec: 'flac',
								bitrate: 800,
								album_name: 'Visions',
								artist_name: 'Grimes'
							},
							{
								navidrome_id: 'n2',
								title: 'Circumambient',
								track_number: 5,
								disc_number: 1,
								duration_seconds: 223,
								codec: 'flac',
								bitrate: 800,
								album_name: 'Visions',
								artist_name: 'Grimes'
							},
							{
								navidrome_id: 'n3',
								title: 'Ambrosia',
								track_number: 1,
								disc_number: 2,
								duration_seconds: 213,
								codec: 'flac',
								bitrate: 800,
								album_name: 'Visions',
								artist_name: 'Grimes'
							},
							{
								navidrome_id: 'n4',
								title: 'Be a Body (Baarsden rework)',
								track_number: 5,
								disc_number: 2,
								duration_seconds: 204,
								codec: 'flac',
								bitrate: 800,
								album_name: 'Visions',
								artist_name: 'Grimes'
							}
						]
					})
				);
			}

			return Promise.resolve(jsonResponse({}));
		});
	});

	it('renders visible grouped track rows alongside source bars', async () => {
		expect.assertions(6);
		render(AlbumPage, {
			props: { data: { albumId } }
		} as Parameters<typeof render<typeof AlbumPage>>[1]);

		await expect.element(page.getByText('Local Files')).toBeVisible();
		await expect.element(page.getByText('Navidrome')).toBeVisible();
		await expect.element(page.getByText('Disc 1')).toBeVisible();
		await expect.element(page.getByText('Disc 2')).toBeVisible();
		await expect.element(page.getByText('Infinite ❤️ Without Fulfillment')).toBeVisible();
		await expect.element(page.getByText('Be a Body (Baarsden rework)')).toBeVisible();
	});

	it('does not refetch tracks when the tracks cache is fresh but basic metadata is stale', async () => {
		expect.assertions(2);
		// eslint-disable-next-line @typescript-eslint/no-explicit-any -- test mock with generic cache type
		mockHydrateDetailCacheEntry.mockImplementation(({ cache, onHydrate }: any) => {
			if (cache === mockAlbumBasicCache) {
				onHydrate({
					title: 'Visions',
					musicbrainz_id: albumId,
					artist_name: 'Grimes',
					artist_id: 'artist-1',
					in_library: true,
					requested: false,
					cover_url: null
				});
				return true;
			}

			if (cache === mockAlbumTracksCache) {
				onHydrate({
					tracks: [
						{ position: 1, disc_number: 1, title: 'Infinite ❤️ Without Fulfillment', length: 95327 }
					],
					total_tracks: 1,
					total_length: 95327,
					label: null,
					barcode: null,
					country: null
				});
				return false;
			}

			return true;
		});

		render(AlbumPage, {
			props: { data: { albumId } }
		} as Parameters<typeof render<typeof AlbumPage>>[1]);

		await expect.element(page.getByText('Infinite ❤️ Without Fulfillment')).toBeVisible();
		expect(
			mockPageFetch.mock.calls.some(
				([input]) => typeof input === 'string' && input.endsWith(`/api/v1/albums/${albumId}/tracks`)
			)
		).toBe(false);
	});
});
