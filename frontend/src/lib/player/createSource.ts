import type { PlaybackSource, SourceType } from './types';
import { YouTubePlaybackSource } from './YouTubePlaybackSource';
import { JellyfinPlaybackSource } from './JellyfinPlaybackSource';
import { LocalPlaybackSource } from './LocalPlaybackSource';
import { YOUTUBE_PLAYER_ELEMENT_ID } from '$lib/constants';

export function createPlaybackSource(type: SourceType): PlaybackSource {
	switch (type) {
		case 'youtube':
			return new YouTubePlaybackSource(YOUTUBE_PLAYER_ELEMENT_ID);
		case 'jellyfin':
			return new JellyfinPlaybackSource();
		case 'howler':
			return new LocalPlaybackSource();
		default: {
			const _exhaustive: never = type;
			throw new Error(`Unknown source type: ${_exhaustive}`);
		}
	}
}
