import type { QueueItem, SourceType } from '$lib/player/types';
import { shuffleArray, stampOrigin } from './playerUtils';
import { buildStreamUrlForSource } from './playerSourceResolver';

export interface PlayQueueResult {
	queue: QueueItem[];
	shuffleEnabled: boolean;
	shuffleOrder: number[];
	isPlayerVisible: boolean;
	startIndex: number;
}

export function buildPlayQueueState(
	items: QueueItem[],
	startIndex: number,
	shuffle: boolean
): PlayQueueResult {
	const queue = stampOrigin(items, 'context');
	const shuffleOrder = shuffle ? shuffleArray(items.length) : [];
	const actualStart = shuffle ? shuffleOrder[0] : startIndex;
	return {
		queue,
		shuffleEnabled: shuffle,
		shuffleOrder,
		isPlayerVisible: true,
		startIndex: actualStart
	};
}

export function buildPlayAlbumState(): {
	playbackState: 'loading';
	isSeekable: true;
	isPlayerVisible: true;
	queue: [];
	currentIndex: 0;
	shuffleOrder: [];
} {
	return {
		playbackState: 'loading',
		isSeekable: true,
		isPlayerVisible: true,
		queue: [],
		currentIndex: 0,
		shuffleOrder: []
	};
}

export interface ToggleShuffleResult {
	shuffleEnabled: boolean;
	shuffleOrder: number[];
}

export function computeToggleShuffle(
	queueLength: number,
	currentIndex: number,
	currentlyEnabled: boolean
): ToggleShuffleResult {
	if (!currentlyEnabled) {
		const allIndices = Array.from({ length: queueLength }, (_, i) => i);
		const upcoming = allIndices.filter((i) => i !== currentIndex && i > currentIndex);
		const played = allIndices.filter((i) => i < currentIndex);

		for (let i = upcoming.length - 1; i > 0; i--) {
			const j = Math.floor(Math.random() * (i + 1));
			[upcoming[i], upcoming[j]] = [upcoming[j], upcoming[i]];
		}

		return {
			shuffleEnabled: true,
			shuffleOrder: [...played, currentIndex, ...upcoming]
		};
	}
	return { shuffleEnabled: false, shuffleOrder: [] };
}

export function buildResetState() {
	return {
		nowPlaying: null as null,
		playbackState: 'idle' as const,
		isSeekable: true as const,
		isPlayerVisible: false as const,
		progress: 0,
		duration: 0,
		queue: [] as QueueItem[],
		currentIndex: 0,
		shuffleOrder: [] as number[],
		shuffleEnabled: false
	};
}

export function changeItemSource(
	queue: QueueItem[],
	index: number,
	newSourceType: SourceType
): { newQueue: QueueItem[]; error?: string } {
	if (index < 0 || index >= queue.length) return { newQueue: queue };

	const item = queue[index];
	if (!item.availableSources?.includes(newSourceType)) return { newQueue: queue };

	const resolvedId = item.sourceIds?.[newSourceType];
	if (!resolvedId) return { newQueue: queue, error: 'Source ID unavailable for this track' };

	const streamUrl = buildStreamUrlForSource(newSourceType, resolvedId);
	const newQueue = [...queue];
	newQueue[index] = {
		...item,
		sourceType: newSourceType,
		trackSourceId: resolvedId,
		streamUrl,
		playSessionId: undefined
	};
	return { newQueue };
}

export function updateItemByPlaylistTrackId(
	queue: QueueItem[],
	playlistTrackId: string,
	currentIndex: number,
	newSourceType: SourceType,
	newTrackSourceId: string,
	newFormat?: string
): QueueItem[] | null {
	const index = queue.findIndex((item) => item.playlistTrackId === playlistTrackId);
	if (index < 0 || index === currentIndex) return null;

	const streamUrl = buildStreamUrlForSource(newSourceType, newTrackSourceId);
	const newQueue = [...queue];
	newQueue[index] = {
		...newQueue[index],
		sourceType: newSourceType,
		trackSourceId: newTrackSourceId,
		streamUrl,
		format: newFormat,
		playSessionId: undefined
	};
	return newQueue;
}
