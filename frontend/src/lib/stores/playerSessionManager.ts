import type { NowPlaying, QueueItem, SourceType } from '$lib/player/types';
import {
	getStoredSession,
	storeSessionData,
	normalizeSourceType,
	migrateLegacyItem
} from './playerUtils';
import type { StoredSession } from './playerUtils';

export function persistSession(
	nowPlaying: NowPlaying | null,
	queue: QueueItem[],
	currentIndex: number,
	progress: number,
	shuffleEnabled: boolean,
	shuffleOrder: number[]
): void {
	if (!nowPlaying) {
		storeSessionData(null);
		return;
	}
	storeSessionData({ nowPlaying, queue, currentIndex, progress, shuffleEnabled, shuffleOrder });
}

export function restoreSessionData(): StoredSession | null {
	return getStoredSession();
}

export interface ResumeState {
	nowPlaying: NowPlaying;
	queue: QueueItem[];
	currentIndex: number;
	progress: number;
	shuffleEnabled: boolean;
	shuffleOrder: number[];
	currentItem: QueueItem;
}

export function buildResumeState(session: StoredSession): ResumeState | null {
	const migratedNowPlaying: NowPlaying = {
		...session.nowPlaying,
		sourceType: normalizeSourceType(session.nowPlaying.sourceType as SourceType | 'howler')
	};
	const migratedQueue = session.queue.map((item) =>
		migrateLegacyItem(item as QueueItem & { sourceType: SourceType | 'howler' })
	);

	if (migratedNowPlaying.sourceType === 'youtube') return null;
	if (!migratedQueue.length) return null;

	const currentItem = migratedQueue[session.currentIndex];
	if (!currentItem) return null;

	return {
		nowPlaying: migratedNowPlaying,
		queue: migratedQueue,
		currentIndex: session.currentIndex,
		progress: session.progress,
		shuffleEnabled: session.shuffleEnabled,
		shuffleOrder: session.shuffleOrder,
		currentItem
	};
}
