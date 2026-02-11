import { tick } from 'svelte';
import { playerStore } from '$lib/stores/player.svelte';
import { YouTubePlaybackSource } from '$lib/player/YouTubePlaybackSource';

export type YouTubePlaybackPayload = {
	albumId: string;
	albumName: string;
	artistName: string;
	videoId: string;
	coverUrl?: string | null;
	embedUrl?: string;
	artistId?: string;
};

type LaunchYouTubePlaybackOptions = {
	onLoadError?: (error: unknown) => void;
	stopOnError?: boolean;
};

export async function launchYouTubePlayback(
	payload: YouTubePlaybackPayload,
	options: LaunchYouTubePlaybackOptions = {}
): Promise<void> {
	const { stopOnError = true, onLoadError } = options;

	const source = new YouTubePlaybackSource('yt-player-embed');
	playerStore.playAlbum(source, {
		albumId: payload.albumId,
		albumName: payload.albumName,
		artistName: payload.artistName,
		coverUrl: payload.coverUrl ?? null,
		sourceType: 'youtube',
		videoId: payload.videoId,
		embedUrl: payload.embedUrl ?? `https://www.youtube.com/embed/${payload.videoId}`,
		artistId: payload.artistId
	});

	await tick();

	try {
		await source.load({ videoId: payload.videoId });
	} catch (error) {
		if (stopOnError) {
			playerStore.stop();
		}
		onLoadError?.(error);
		throw error;
	}
}
