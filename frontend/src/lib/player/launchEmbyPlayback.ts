import { playerStore } from '$lib/stores/player.svelte';
import type { PlaybackMeta, QueueItem } from '$lib/player/types';
import type { EmbyTrackInfo } from '$lib/types';
import { getCoverUrl } from '$lib/utils/errorHandling';
import { normalizeCodec } from '$lib/player/queueHelpers';

export function launchEmbyPlayback(
	tracks: EmbyTrackInfo[],
	startIndex: number = 0,
	shuffle: boolean = false,
	meta: PlaybackMeta
): void {
	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);

	const items: QueueItem[] = tracks.map((t) => {
		const format = normalizeCodec(t.codec);
		return {
			trackSourceId: t.emby_id,
			trackName: t.title,
			artistName: meta.artistName,
			trackNumber: t.track_number,
			discNumber: t.disc_number ?? 1,
			albumId: meta.albumId,
			albumName: meta.albumName,
			coverUrl: normalizedCoverUrl,
			sourceType: 'emby' as const,
			artistId: meta.artistId,
			streamUrl: undefined,
			format
		};
	});

	playerStore.playQueue(items, startIndex, shuffle);
}
