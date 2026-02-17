import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { LocalTrackInfo, JellyfinTrackInfo } from '$lib/types';
import type { PlaybackMeta, QueueItem } from '$lib/player/types';

vi.mock('$lib/stores/player.svelte', () => ({
	playerStore: { playQueue: vi.fn() }
}));

vi.mock('$lib/constants', () => ({
	API: {
		stream: {
			local: (id: number | string) => `/api/stream/local/${id}`,
			jellyfin: (id: string, format = 'aac', bitrate = 128000) =>
				`/api/stream/jellyfin/${id}?format=${format}&bitrate=${bitrate}`
		}
	}
}));

import { playerStore } from '$lib/stores/player.svelte';
import { launchLocalPlayback } from './launchLocalPlayback';
import { launchJellyfinPlayback } from './launchJellyfinPlayback';

const meta: PlaybackMeta = {
	albumId: 'album-1',
	albumName: 'Test Album',
	artistName: 'Test Artist',
	coverUrl: '/cover.jpg',
	artistId: 'artist-1'
};

describe('launchLocalPlayback', () => {
	beforeEach(() => vi.clearAllMocks());

	it('maps LocalTrackInfo[] to QueueItem[] with sourceType howler', () => {
		const tracks: LocalTrackInfo[] = [
			{
				track_file_id: 42,
				title: 'Song A',
				track_number: 1,
				format: 'FLAC',
				size_bytes: 30_000_000
			}
		];

		launchLocalPlayback(tracks, 0, false, meta);

		const call = vi.mocked(playerStore.playQueue).mock.calls[0];
		const items: QueueItem[] = call[0];

		expect(items).toHaveLength(1);
		expect(items[0]).toEqual(
			expect.objectContaining({
				videoId: '42',
				trackName: 'Song A',
				sourceType: 'howler',
				streamUrl: '/api/stream/local/42',
				format: 'flac'
			})
		);
	});

	it('passes startIndex and shuffle through to playerStore', () => {
		const tracks: LocalTrackInfo[] = [
			{
				track_file_id: 1,
				title: 'A',
				track_number: 1,
				format: 'mp3',
				size_bytes: 5_000_000
			},
			{
				track_file_id: 2,
				title: 'B',
				track_number: 2,
				format: 'mp3',
				size_bytes: 5_000_000
			}
		];

		launchLocalPlayback(tracks, 1, true, meta);

		expect(playerStore.playQueue).toHaveBeenCalledWith(expect.any(Array), 1, true);
	});
});

describe('launchJellyfinPlayback', () => {
	beforeEach(() => vi.clearAllMocks());

	it('maps JellyfinTrackInfo[] to QueueItem[] with sourceType jellyfin', () => {
		const tracks: JellyfinTrackInfo[] = [
			{
				jellyfin_id: 'jf-abc',
				title: 'Jelly Song',
				track_number: 3,
				duration_seconds: 240,
				album_name: 'Test Album',
				artist_name: 'Test Artist',
				codec: 'FLAC'
			}
		];

		launchJellyfinPlayback(tracks, 0, false, meta);

		const call = vi.mocked(playerStore.playQueue).mock.calls[0];
		const items: QueueItem[] = call[0];

		expect(items).toHaveLength(1);
		expect(items[0]).toEqual(
			expect.objectContaining({
				videoId: 'jf-abc',
				trackName: 'Jelly Song',
				sourceType: 'jellyfin',
				format: 'flac'
			})
		);
	});

	it('aligns streamUrl format parameter with QueueItem format', () => {
		const tracks: JellyfinTrackInfo[] = [
			{
				jellyfin_id: 'jf-abc',
				title: 'Jelly Song',
				track_number: 3,
				duration_seconds: 240,
				album_name: 'Test Album',
				artist_name: 'Test Artist',
				codec: 'FLAC'
			}
		];

		launchJellyfinPlayback(tracks, 0, false, meta);

		const call = vi.mocked(playerStore.playQueue).mock.calls[0];
		const item: QueueItem = call[0][0];

		expect(item.streamUrl).toBe('/api/stream/jellyfin/jf-abc?format=flac&bitrate=128000');
		expect(item.format).toBe('flac');
	});

	it('falls back to aac when codec is null', () => {
		const tracks: JellyfinTrackInfo[] = [
			{
				jellyfin_id: 'jf-xyz',
				title: 'No Codec',
				track_number: 1,
				duration_seconds: 180,
				album_name: 'Test Album',
				artist_name: 'Test Artist',
				codec: null
			}
		];

		launchJellyfinPlayback(tracks, 0, false, meta);

		const call = vi.mocked(playerStore.playQueue).mock.calls[0];
		const items: QueueItem[] = call[0];

		expect(items[0].format).toBe('aac');
	});

	it('falls back to aac when codec is undefined', () => {
		const tracks: JellyfinTrackInfo[] = [
			{
				jellyfin_id: 'jf-xyz',
				title: 'No Codec',
				track_number: 1,
				duration_seconds: 180,
				album_name: 'Test Album',
				artist_name: 'Test Artist'
			}
		];

		launchJellyfinPlayback(tracks, 0, false, meta);

		const call = vi.mocked(playerStore.playQueue).mock.calls[0];
		const items: QueueItem[] = call[0];

		expect(items[0].format).toBe('aac');
	});
});
