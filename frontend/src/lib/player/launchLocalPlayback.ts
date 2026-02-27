import { playerStore } from '$lib/stores/player.svelte';
import { API } from '$lib/constants';
import type { PlaybackMeta, QueueItem } from '$lib/player/types';
import type { LocalTrackInfo } from '$lib/types';
import { getCoverUrl } from '$lib/utils/errorHandling';

export function launchLocalPlayback(
	tracks: LocalTrackInfo[],
	startIndex: number = 0,
	shuffle: boolean = false,
	meta: PlaybackMeta
): void {
	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);

	const items: QueueItem[] = tracks.map((t) => ({
		videoId: String(t.track_file_id),
		trackName: t.title,
		artistName: meta.artistName,
		trackNumber: t.track_number,
		albumId: meta.albumId,
		albumName: meta.albumName,
		coverUrl: normalizedCoverUrl,
		sourceType: 'howler',
		artistId: meta.artistId,
		streamUrl: API.stream.local(t.track_file_id),
		format: t.format.toLowerCase()
	}));

	playerStore.playQueue(items, startIndex, shuffle);
}
