import { playerStore } from '$lib/stores/player.svelte';
import type { QueueItem } from '$lib/player/types';
import type { YouTubeTrackLink } from '$lib/types';

export type TrackQueueOptions = {
	albumId: string;
	albumName: string;
	artistName: string;
	coverUrl: string | null;
	artistId?: string;
};

export function launchTrackPlayback(
	trackLinks: YouTubeTrackLink[],
	startIndex: number = 0,
	shuffle: boolean = false,
	options: TrackQueueOptions
): void {
	const items: QueueItem[] = trackLinks.map((tl) => ({
		videoId: tl.video_id,
		trackName: tl.track_name,
		artistName: options.artistName,
		trackNumber: tl.track_number,
		albumId: options.albumId,
		albumName: options.albumName,
		coverUrl: options.coverUrl,
		sourceType: 'youtube',
		artistId: options.artistId
	}));

	playerStore.playQueue(items, startIndex, shuffle);
}
