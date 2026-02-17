import { playerStore } from '$lib/stores/player.svelte';
import { API } from '$lib/constants';
import type { PlaybackMeta, QueueItem } from '$lib/player/types';
import type { LocalTrackInfo } from '$lib/types';

export function launchLocalPlayback(
	tracks: LocalTrackInfo[],
	startIndex: number = 0,
	shuffle: boolean = false,
	meta: PlaybackMeta
): void {
	const items: QueueItem[] = tracks.map((t) => ({
		videoId: String(t.track_file_id),
		trackName: t.title,
		artistName: meta.artistName,
		trackNumber: t.track_number,
		albumId: meta.albumId,
		albumName: meta.albumName,
		coverUrl: meta.coverUrl,
		sourceType: 'howler',
		artistId: meta.artistId,
		streamUrl: API.stream.local(t.track_file_id),
		format: t.format.toLowerCase()
	}));

	playerStore.playQueue(items, startIndex, shuffle);
}
