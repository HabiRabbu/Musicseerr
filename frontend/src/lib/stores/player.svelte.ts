import type { PlaybackSource, PlaybackState, NowPlaying, QueueItem, SourceType } from '$lib/player/types';
import { createPlaybackSource } from '$lib/player/createSource';
import { playbackToast } from '$lib/stores/playbackToast.svelte';

const VOLUME_STORAGE_KEY = 'musicseerr_player_volume';
const SESSION_STORAGE_KEY = 'musicseerr_player_session';
const MAX_CONSECUTIVE_ERRORS = 3;
const ERROR_SKIP_DELAY_MS = 2000;
const SESSION_PERSIST_INTERVAL_MS = 5000;

type StoredSession = {
	nowPlaying: NowPlaying;
	queue: QueueItem[];
	currentIndex: number;
	progress: number;
	shuffleEnabled: boolean;
	shuffleOrder: number[];
};

function getStoredVolume(): number {
	try {
		const stored = localStorage.getItem(VOLUME_STORAGE_KEY);
		if (stored !== null) return Math.max(0, Math.min(100, Number(stored)));
	} catch {}
	return 75;
}

function storeVolume(volume: number): void {
	try {
		localStorage.setItem(VOLUME_STORAGE_KEY, String(volume));
	} catch {}
}

function getStoredSession(): StoredSession | null {
	try {
		const stored = localStorage.getItem(SESSION_STORAGE_KEY);
		if (!stored) return null;
		const parsed = JSON.parse(stored);
		if (parsed && parsed.nowPlaying) return parsed as StoredSession;
	} catch {}
	return null;
}

function storeSessionData(data: StoredSession | null): void {
	try {
		if (data) {
			localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data));
		} else {
			localStorage.removeItem(SESSION_STORAGE_KEY);
		}
	} catch {}
}

function shuffleArray(length: number): number[] {
	const arr = Array.from({ length }, (_, i) => i);
	for (let i = arr.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[arr[i], arr[j]] = [arr[j], arr[i]];
	}
	return arr;
}

function createPlayerStore() {
	let currentSource = $state<PlaybackSource | null>(null);
	let nowPlaying = $state<NowPlaying | null>(null);
	let playbackState = $state<PlaybackState>('idle');
	let volume = $state(getStoredVolume());
	let progress = $state(0);
	let duration = $state(0);
	let isPlayerVisible = $state(false);
	let loadGeneration = 0;

	let queue = $state<QueueItem[]>([]);
	let currentIndex = $state(0);
	let shuffleEnabled = $state(false);
	let shuffleOrder = $state<number[]>([]);

	let consecutiveErrors = 0;
	let errorSkipTimeout: ReturnType<typeof setTimeout> | null = null;
	let lastPersistTime = 0;

	const isPlaying = $derived(playbackState === 'playing');
	const isBuffering = $derived(playbackState === 'buffering' || playbackState === 'loading');
	const hasQueue = $derived(queue.length > 0);

	const hasNext = $derived.by(() => {
		if (queue.length <= 1) return false;
		if (shuffleEnabled) {
			const shuffleIdx = shuffleOrder.indexOf(currentIndex);
			return shuffleIdx < shuffleOrder.length - 1;
		}
		return currentIndex < queue.length - 1;
	});

	const hasPrevious = $derived.by(() => {
		if (queue.length <= 1) return false;
		if (shuffleEnabled) {
			const shuffleIdx = shuffleOrder.indexOf(currentIndex);
			return shuffleIdx > 0;
		}
		return currentIndex > 0;
	});

	const currentQueueItem = $derived(queue.length > 0 ? queue[currentIndex] : null);
	const queueLength = $derived(queue.length);
	const currentTrackNumber = $derived(currentIndex + 1);

	function getNextIndex(): number | null {
		if (queue.length <= 1) return null;
		if (shuffleEnabled) {
			const shuffleIdx = shuffleOrder.indexOf(currentIndex);
			if (shuffleIdx < shuffleOrder.length - 1) return shuffleOrder[shuffleIdx + 1];
			return null;
		}
		if (currentIndex < queue.length - 1) return currentIndex + 1;
		return null;
	}

	function getPreviousIndex(): number | null {
		if (queue.length <= 1) return null;
		if (shuffleEnabled) {
			const shuffleIdx = shuffleOrder.indexOf(currentIndex);
			if (shuffleIdx > 0) return shuffleOrder[shuffleIdx - 1];
			return null;
		}
		if (currentIndex > 0) return currentIndex - 1;
		return null;
	}

	async function loadQueueItem(index: number): Promise<void> {
		const item = queue[index];
		if (!item) return;

		if (errorSkipTimeout) {
			clearTimeout(errorSkipTimeout);
			errorSkipTimeout = null;
		}

		currentSource?.destroy();
		currentIndex = index;
		playbackState = 'loading';
		progress = 0;
		duration = 0;

		const gen = ++loadGeneration;
		const source = createPlaybackSource(item.sourceType);
		currentSource = source;

		const metadata: NowPlaying = {
			albumId: item.albumId,
			albumName: item.albumName,
			artistName: item.artistName,
			coverUrl: item.coverUrl,
			sourceType: item.sourceType,
			trackSourceId: item.trackSourceId,
			trackName: item.trackName,
			artistId: item.artistId,
			streamUrl: item.streamUrl,
			format: item.format,
		};
		nowPlaying = metadata;
		persistSession();
		subscribeToSource(source, gen);
		source.setVolume(volume);

		try {
			await source.load({
				trackSourceId: item.trackSourceId,
				url: item.streamUrl,
				format: item.format,
			});
			if (gen === loadGeneration) {
				source.play();
			}
		} catch {
			if (gen === loadGeneration) handleTrackError(gen);
		}
	}

	function handleTrackError(gen: number): void {
		if (gen !== loadGeneration) return;
		consecutiveErrors++;
		playbackState = 'error';

		const trackName = nowPlaying?.trackName ?? 'Unknown track';

		if (consecutiveErrors >= MAX_CONSECUTIVE_ERRORS) {
			playbackToast.show(`Multiple tracks failed — playback stopped`, 'error');
			currentSource?.destroy();
			currentSource = null;
			nowPlaying = null;
			playbackState = 'idle';
			isPlayerVisible = false;
			progress = 0;
			duration = 0;
			queue = [];
			currentIndex = 0;
			shuffleOrder = [];
			shuffleEnabled = false;
			consecutiveErrors = 0;
			storeSessionData(null);
			return;
		}

		const nextIdx = getNextIndex();
		if (nextIdx !== null) {
			playbackToast.show(`"${trackName}" unavailable — skipping…`, 'warning');
			errorSkipTimeout = setTimeout(() => {
				errorSkipTimeout = null;
				if (gen === loadGeneration) void loadQueueItem(nextIdx);
			}, ERROR_SKIP_DELAY_MS);
		} else {
			playbackToast.show(`"${trackName}" unavailable`, 'error');
		}
	}

	function prefetchNextTrack(): void {
		const nextIdx = getNextIndex();
		if (nextIdx === null) return;
		const nextItem = queue[nextIdx];
		if (!nextItem?.streamUrl) return;
		if (nextItem.sourceType === 'youtube') return;
		void fetch(nextItem.streamUrl, { method: 'HEAD' }).catch(() => {});
	}

	function persistSession(): void {
		if (!nowPlaying) {
			storeSessionData(null);
			return;
		}
		storeSessionData({
			nowPlaying,
			queue,
			currentIndex,
			progress,
			shuffleEnabled,
			shuffleOrder,
		});
	}

	function subscribeToSource(source: PlaybackSource, gen: number): void {
		source.onStateChange((state) => {
			if (gen !== loadGeneration) return;
			playbackState = state;
			if (state === 'playing') {
				consecutiveErrors = 0;
				prefetchNextTrack();
			}
			if (state === 'ended') {
				const nextIdx = getNextIndex();
				if (nextIdx !== null) {
					void loadQueueItem(nextIdx);
				} else {
					isPlayerVisible = false;
					source.destroy();
					currentSource = null;
					nowPlaying = null;
					playbackState = 'idle';
					progress = 0;
					duration = 0;
					queue = [];
					currentIndex = 0;
					shuffleOrder = [];
					storeSessionData(null);
				}
			}
		});

		source.onProgress((currentTime, totalDuration) => {
			if (gen !== loadGeneration) return;
			progress = currentTime;
			duration = totalDuration;
			const now = Date.now();
			if (now - lastPersistTime >= SESSION_PERSIST_INTERVAL_MS) {
				lastPersistTime = now;
				persistSession();
			}
		});

		source.onError(() => {
			if (gen !== loadGeneration) return;
			handleTrackError(gen);
		});
	}

	function showQueueMutationToast(action: 'queue' | 'next', count: number): void {
		const label = count === 1 ? 'track' : 'tracks';
		if (action === 'queue') {
			playbackToast.show(
				count === 1 ? 'Added track to queue' : `Added ${count} ${label} to queue`,
				'info'
			);
			return;
		}
		playbackToast.show(
			count === 1 ? 'Queued track to play next' : `Queued ${count} ${label} to play next`,
			'info'
		);
	}

	return {
		get currentSource() {
			return currentSource;
		},
		get nowPlaying() {
			return nowPlaying;
		},
		get playbackState() {
			return playbackState;
		},
		get isPlaying() {
			return isPlaying;
		},
		get isBuffering() {
			return isBuffering;
		},
		get volume() {
			return volume;
		},
		get progress() {
			return progress;
		},
		get duration() {
			return duration;
		},
		get isPlayerVisible() {
			return isPlayerVisible;
		},
		get hasQueue() {
			return hasQueue;
		},
		get hasNext() {
			return hasNext;
		},
		get hasPrevious() {
			return hasPrevious;
		},
		get shuffleEnabled() {
			return shuffleEnabled;
		},
		get queue() {
			return queue;
		},
		get currentIndex() {
			return currentIndex;
		},
		get currentQueueItem() {
			return currentQueueItem;
		},
		get queueLength() {
			return queueLength;
		},
		get upcomingQueueLength() {
			if (queue.length === 0) return 0;
			if (shuffleEnabled) {
				const shuffleIdx = shuffleOrder.indexOf(currentIndex);
				if (shuffleIdx < 0) return Math.max(0, queue.length - 1);
				return Math.max(0, shuffleOrder.length - shuffleIdx - 1);
			}
			return Math.max(0, queue.length - currentIndex - 1);
		},
		get currentTrackNumber() {
			return currentTrackNumber;
		},
		get shuffleOrder() {
			return shuffleOrder;
		},

		playAlbum(source: PlaybackSource, metadata: NowPlaying): void {
			currentSource?.destroy();
			const gen = ++loadGeneration;
			currentSource = source;
			nowPlaying = metadata;
			playbackState = 'loading';
			isPlayerVisible = true;
			queue = [];
			currentIndex = 0;
			shuffleOrder = [];
			consecutiveErrors = 0;
			subscribeToSource(source, gen);
			source.setVolume(volume);
			persistSession();
		},

		playQueue(items: QueueItem[], startIndex: number = 0, shuffle: boolean = false): void {
			if (items.length === 0) return;
			queue = items;
			shuffleEnabled = shuffle;
			isPlayerVisible = true;
			consecutiveErrors = 0;

			if (shuffle) {
				shuffleOrder = shuffleArray(items.length);
				const actualStart = shuffleOrder[0];
				void loadQueueItem(actualStart);
			} else {
				void loadQueueItem(startIndex);
			}
		},

		nextTrack(): void {
			const nextIdx = getNextIndex();
			if (nextIdx !== null) {
				void loadQueueItem(nextIdx);
			}
		},

		previousTrack(): void {
			const prevIdx = getPreviousIndex();
			if (prevIdx !== null) {
				void loadQueueItem(prevIdx);
			}
		},

		toggleShuffle(): void {
			shuffleEnabled = !shuffleEnabled;
			if (shuffleEnabled) {
				shuffleOrder = shuffleArray(queue.length);
				const idx = shuffleOrder.indexOf(currentIndex);
				if (idx > 0) {
					shuffleOrder.splice(idx, 1);
					shuffleOrder.unshift(currentIndex);
				} else if (idx === -1) {
					shuffleOrder.unshift(currentIndex);
				}
			} else {
				shuffleOrder = [];
			}
		},

		jumpToTrack(index: number): void {
			if (index < 0 || index >= queue.length) return;
			void loadQueueItem(index);
		},

		addToQueue(item: QueueItem): void {
			if (queue.length === 0) {
				this.playQueue([item], 0, false);
				showQueueMutationToast('queue', 1);
				return;
			}

			queue = [...queue, item];
			if (shuffleEnabled) {
				shuffleOrder = [...shuffleOrder, queue.length - 1];
			}
			persistSession();
			showQueueMutationToast('queue', 1);
		},

		addMultipleToQueue(items: QueueItem[]): void {
			if (items.length === 0) return;

			if (queue.length === 0) {
				this.playQueue(items, 0, false);
				showQueueMutationToast('queue', items.length);
				return;
			}

			const startIdx = queue.length;
			queue = [...queue, ...items];
			if (shuffleEnabled) {
				const newIndices = items.map((_, i) => startIdx + i);
				shuffleOrder = [...shuffleOrder, ...newIndices];
			}
			persistSession();
			showQueueMutationToast('queue', items.length);
		},

		playNext(item: QueueItem): void {
			if (queue.length === 0) {
				this.playQueue([item], 0, false);
				showQueueMutationToast('next', 1);
				return;
			}

			const insertAt = currentIndex + 1;
			const newQueue = [...queue];
			newQueue.splice(insertAt, 0, item);
			queue = newQueue;
			if (shuffleEnabled) {
				const updated = shuffleOrder.map((i) => (i >= insertAt ? i + 1 : i));
				const shuffleIdx = updated.indexOf(currentIndex);
				updated.splice(shuffleIdx + 1, 0, insertAt);
				shuffleOrder = updated;
			}
			persistSession();
			showQueueMutationToast('next', 1);
		},

		playMultipleNext(items: QueueItem[]): void {
			if (items.length === 0) return;

			if (queue.length === 0) {
				this.playQueue(items, 0, false);
				showQueueMutationToast('next', items.length);
				return;
			}

			const insertAt = currentIndex + 1;
			const newQueue = [...queue];
			newQueue.splice(insertAt, 0, ...items);
			queue = newQueue;
			if (shuffleEnabled) {
				const updated = shuffleOrder.map((i) => (i >= insertAt ? i + items.length : i));
				const shuffleIdx = updated.indexOf(currentIndex);
				const newIndices = items.map((_, i) => insertAt + i);
				updated.splice(shuffleIdx + 1, 0, ...newIndices);
				shuffleOrder = updated;
			}
			persistSession();
			showQueueMutationToast('next', items.length);
		},

		removeFromQueue(index: number): void {
			if (index < 0 || index >= queue.length) return;
			if (queue.length <= 1) {
				this.stop();
				return;
			}
			const wasPlaying = index === currentIndex;
			const newQueue = queue.filter((_, i) => i !== index);
			if (shuffleEnabled) {
				shuffleOrder = shuffleOrder
					.filter((i) => i !== index)
					.map((i) => (i > index ? i - 1 : i));
			}
			if (wasPlaying) {
				const newIndex = Math.min(index, newQueue.length - 1);
				queue = newQueue;
				currentIndex = newIndex;
				void loadQueueItem(newIndex);
			} else {
				const newCurrentIndex = currentIndex > index ? currentIndex - 1 : currentIndex;
				queue = newQueue;
				currentIndex = newCurrentIndex;
				persistSession();
			}
		},

		reorderQueue(fromIndex: number, toIndex: number): void {
			if (fromIndex === toIndex) return;
			if (fromIndex < 0 || fromIndex >= queue.length) return;
			if (toIndex < 0 || toIndex >= queue.length) return;
			const newQueue = [...queue];
			const [moved] = newQueue.splice(fromIndex, 1);
			newQueue.splice(toIndex, 0, moved);
			let newCurrentIndex = currentIndex;
			if (currentIndex === fromIndex) {
				newCurrentIndex = toIndex;
			} else if (fromIndex < currentIndex && toIndex >= currentIndex) {
				newCurrentIndex = currentIndex - 1;
			} else if (fromIndex > currentIndex && toIndex <= currentIndex) {
				newCurrentIndex = currentIndex + 1;
			}
			queue = newQueue;
			currentIndex = newCurrentIndex;
			persistSession();
		},

		reorderShuffleOrder(fromPos: number, toPos: number): void {
			if (fromPos === toPos) return;
			const newOrder = [...shuffleOrder];
			const [moved] = newOrder.splice(fromPos, 1);
			newOrder.splice(toPos, 0, moved);
			shuffleOrder = newOrder;
			persistSession();
		},

		clearQueue(): void {
			if (queue.length === 0) {
				this.stop();
				return;
			}

			const currentItem = queue[currentIndex];
			if (!currentItem) {
				this.stop();
				return;
			}

			queue = [currentItem];
			currentIndex = 0;
			shuffleEnabled = false;
			shuffleOrder = [];
			persistSession();
		},

		changeTrackSource(index: number, newSourceType: SourceType): void {
			if (index < 0 || index >= queue.length) return;
			if (index === currentIndex) {
				playbackToast.show('Cannot change source for the currently playing track', 'warning');
				return;
			}

			const item = queue[index];
			if (!item.availableSources?.includes(newSourceType)) return;

			let streamUrl: string | undefined;
			if (newSourceType === 'howler') {
				streamUrl = `/api/stream/local/${item.trackSourceId}`;
			} else if (newSourceType === 'jellyfin') {
				const format = item.format ?? 'aac';
				streamUrl = `/api/stream/jellyfin/${item.trackSourceId}?format=${format}&bitrate=128000`;
			}

			const newQueue = [...queue];
			newQueue[index] = { ...item, sourceType: newSourceType, streamUrl };
			queue = newQueue;
			persistSession();
		},

		play(): void {
			currentSource?.play();
		},

		pause(): void {
			currentSource?.pause();
			persistSession();
		},

		togglePlay(): void {
			if (isPlaying) {
				currentSource?.pause();
			} else {
				currentSource?.play();
			}
		},

		seekTo(seconds: number): void {
			currentSource?.seekTo(seconds);
			progress = seconds;
			persistSession();
		},

		setVolume(level: number): void {
			const clamped = Math.max(0, Math.min(100, level));
			volume = clamped;
			currentSource?.setVolume(clamped);
			storeVolume(clamped);
		},

		stop(): void {
			if (errorSkipTimeout) {
				clearTimeout(errorSkipTimeout);
				errorSkipTimeout = null;
			}
			loadGeneration++;
			currentSource?.destroy();
			currentSource = null;
			nowPlaying = null;
			playbackState = 'idle';
			isPlayerVisible = false;
			progress = 0;
			duration = 0;
			queue = [];
			currentIndex = 0;
			shuffleOrder = [];
			shuffleEnabled = false;
			consecutiveErrors = 0;
			storeSessionData(null);
		},

		restoreSession(): StoredSession | null {
			return getStoredSession();
		},

		resumeSession(): void {
			const session = getStoredSession();
			if (!session) return;
			const { nowPlaying: stored, queue: storedQueue, currentIndex: storedIndex, progress: storedProgress, shuffleEnabled: storedShuffle, shuffleOrder: storedOrder } = session;
			if (stored.sourceType === 'youtube') return;
			if (!storedQueue.length) return;

			queue = storedQueue;
			shuffleEnabled = storedShuffle;
			shuffleOrder = storedOrder;
			isPlayerVisible = true;
			consecutiveErrors = 0;

			const item = storedQueue[storedIndex];
			if (!item) return;

			currentSource?.destroy();
			currentIndex = storedIndex;
			playbackState = 'loading';
			progress = 0;
			duration = 0;

			const gen = ++loadGeneration;
			const source = createPlaybackSource(item.sourceType);
			currentSource = source;
			nowPlaying = stored;
			subscribeToSource(source, gen);
			source.setVolume(volume);

			void source.load({
				trackSourceId: item.trackSourceId,
				url: item.streamUrl,
				format: item.format,
			}).then(() => {
				if (gen !== loadGeneration) return;
				playbackState = 'paused';
				duration = source.getDuration();
				if (storedProgress > 0) {
					source.seekTo(storedProgress);
					progress = storedProgress;
				}
			}).catch(() => {
				if (gen === loadGeneration) {
					playbackState = 'error';
					storeSessionData(null);
				}
			});
		}
	};
}

export const playerStore = createPlayerStore();
