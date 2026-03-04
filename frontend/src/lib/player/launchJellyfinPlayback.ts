import { playerStore } from '$lib/stores/player.svelte';
import { API } from '$lib/constants';
import type { PlaybackMeta, QueueItem } from '$lib/player/types';
import type { JellyfinTrackInfo } from '$lib/types';
import { getCoverUrl } from '$lib/utils/errorHandling';

const SUPPORTED_CODECS = new Set(['aac', 'mp3', 'opus', 'flac', 'wav', 'wma', 'vorbis', 'alac']);
const CODEC_ALIASES: Record<string, string> = {
	alac: 'flac',
	wma: 'aac'
};

function normalizeCodec(codec: string | undefined | null): string {
	const raw = codec?.toLowerCase() ?? 'aac';
	if (CODEC_ALIASES[raw]) return CODEC_ALIASES[raw];
	if (SUPPORTED_CODECS.has(raw)) return raw;
	return 'aac';
}

export function launchJellyfinPlayback(
	tracks: JellyfinTrackInfo[],
	startIndex: number = 0,
	shuffle: boolean = false,
	meta: PlaybackMeta
): void {
	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);

	const items: QueueItem[] = tracks.map((t) => {
		const format = normalizeCodec(t.codec);
		return {
			trackSourceId: t.jellyfin_id,
			trackName: t.title,
			artistName: meta.artistName,
			trackNumber: t.track_number,
			albumId: meta.albumId,
			albumName: meta.albumName,
			coverUrl: normalizedCoverUrl,
			sourceType: 'jellyfin' as const,
			artistId: meta.artistId,
			streamUrl: API.stream.jellyfin(t.jellyfin_id, format),
			format
		};
	});

	playerStore.playQueue(items, startIndex, shuffle);
}
