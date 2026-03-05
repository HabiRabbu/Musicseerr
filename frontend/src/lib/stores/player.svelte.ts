import type { PlaybackSource, PlaybackState, NowPlaying, QueueItem, QueueOrigin, SourceType } from '$lib/player/types';
import { createPlaybackSource } from '$lib/player/createSource';
import { API } from '$lib/constants';
import { reportProgress as reportJellyfinProgress, reportStop as reportJellyfinStop, startSession as startJellyfinSession } from '$lib/player/jellyfinPlaybackApi';
import { playbackToast } from '$lib/stores/playbackToast.svelte';

const VOLUME_STORAGE_KEY = 'musicseerr_player_volume';
const SESSION_STORAGE_KEY = 'musicseerr_player_session';
const MAX_CONSECUTIVE_ERRORS = 3;
const ERROR_SKIP_DELAY_MS = 2000;
const MAX_HISTORY_LENGTH = 3;
const SESSION_PERSIST_INTERVAL_MS = 5000;
const JELLYFIN_REPORT_INTERVAL_MS = 10_000;
const MAX_JELLYFIN_REPORT_FAILURES = 3;

type JellyfinPlaybackUrlResponse = {
	url: string;
	seekable: boolean;
	playSessionId: string;
};

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

function stampOrigin(items: QueueItem[], origin: QueueOrigin): QueueItem[] {
	return items.map((item) => ({ ...item, queueOrigin: origin }));
}

function stampSingleOrigin(item: QueueItem, origin: QueueOrigin): QueueItem {
	return { ...item, queueOrigin: origin };
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
	let isSeekable = $state(true);
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
	let jellyfinReportInterval: ReturnType<typeof setInterval> | null = null;
	let jellyfinConsecutiveReportFailures = 0;
	let beforeUnloadRegistered = false;

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

	function cleanupPlayedTracks(): void {
		if (queue.length <= 1) return;

		let playedIndices: number[];
		if (shuffleEnabled) {
			const currentShufflePos = shuffleOrder.indexOf(currentIndex);
			if (currentShufflePos <= 0) return;
			playedIndices = shuffleOrder.slice(0, currentShufflePos);
		} else {
			if (currentIndex <= 0) return;
			playedIndices = Array.from({ length: currentIndex }, (_, i) => i);
		}

		const toRemove = new Set<number>();

		for (const idx of playedIndices) {
			if (queue[idx]?.queueOrigin === 'manual') {
				toRemove.add(idx);
			}
		}

		const remainingPlayed = playedIndices.filter((idx) => !toRemove.has(idx));
		const excess = remainingPlayed.length - MAX_HISTORY_LENGTH;
		if (excess > 0) {
			for (let i = 0; i < excess; i++) {
				toRemove.add(remainingPlayed[i]);
			}
		}

		if (toRemove.size === 0) return;

		const indexMap = new Map<number, number>();
		let shift = 0;
		for (let i = 0; i < queue.length; i++) {
			if (toRemove.has(i)) {
				shift++;
			} else {
				indexMap.set(i, i - shift);
			}
		}

		const newQueue = queue.filter((_, i) => !toRemove.has(i));
		const newCurrentIndex = indexMap.get(currentIndex) ?? 0;

		if (shuffleEnabled) {
			shuffleOrder = shuffleOrder
				.filter((i) => !toRemove.has(i))
				.map((i) => indexMap.get(i)!);
		}

		queue = newQueue;
		currentIndex = newCurrentIndex;
		persistSession();
	}

	function normalizeSourceType(sourceType: SourceType | 'howler'): SourceType {
		return sourceType === 'howler' ? 'local' : sourceType;
	}

	function migrateLegacyItem(item: QueueItem & { sourceType: SourceType | 'howler' }): QueueItem {
		const sourceType = normalizeSourceType(item.sourceType);
		const availableSources = item.availableSources?.map((source) => normalizeSourceType(source as SourceType | 'howler'));
		return {
			...item,
			sourceType,
			availableSources,
			queueOrigin: item.queueOrigin ?? 'context',
		};
	}

	function getCurrentJellyfinItem(): QueueItem | null {
		const item = queue[currentIndex];
		if (!item || item.sourceType !== 'jellyfin') return null;
		return item;
	}

	function clearJellyfinProgressReporting(): void {
		if (jellyfinReportInterval) {
			clearInterval(jellyfinReportInterval);
			jellyfinReportInterval = null;
		}
		jellyfinConsecutiveReportFailures = 0;
	}

	function handleBeforeUnload(): void {
		const current = getCurrentJellyfinItem();
		if (!current?.playSessionId || typeof navigator === 'undefined' || typeof navigator.sendBeacon !== 'function') {
			return;
		}

		const payload = new Blob([
			JSON.stringify({
				play_session_id: current.playSessionId,
				position_seconds: progress,
			})
		], { type: 'application/json' });

		navigator.sendBeacon(API.stream.jellyfinStop(current.trackSourceId), payload);
	}

	function registerBeforeUnloadStop(): void {
		if (beforeUnloadRegistered || typeof window === 'undefined') return;
		window.addEventListener('beforeunload', handleBeforeUnload);
		beforeUnloadRegistered = true;
	}

	function unregisterBeforeUnloadStop(): void {
		if (!beforeUnloadRegistered || typeof window === 'undefined') return;
		window.removeEventListener('beforeunload', handleBeforeUnload);
		beforeUnloadRegistered = false;
	}

	async function stopJellyfinSession(item: QueueItem | null, positionSeconds: number): Promise<void> {
		clearJellyfinProgressReporting();
		unregisterBeforeUnloadStop();

		if (!item || item.sourceType !== 'jellyfin' || !item.playSessionId) return;
		await reportJellyfinStop(item.trackSourceId, item.playSessionId, positionSeconds);
	}

	function startJellyfinProgressReportingFor(item: QueueItem): void {
		clearJellyfinProgressReporting();
		if (!item.playSessionId) return;

		jellyfinReportInterval = setInterval(async () => {
			const current = getCurrentJellyfinItem();
			if (!current?.playSessionId) {
				clearJellyfinProgressReporting();
				return;
			}

			try {
				const ok = await reportJellyfinProgress(
					current.trackSourceId,
					current.playSessionId,
					progress,
					playbackState !== 'playing'
				);
				if (ok) {
					jellyfinConsecutiveReportFailures = 0;
					return;
				}

				jellyfinConsecutiveReportFailures += 1;
				if (jellyfinConsecutiveReportFailures >= MAX_JELLYFIN_REPORT_FAILURES) {
					clearJellyfinProgressReporting();
				}
			} catch {}
		}, JELLYFIN_REPORT_INTERVAL_MS);
	}

	async function resolveSourceForItem(item: QueueItem, index: number): Promise<{ source: PlaybackSource; loadUrl: string | undefined }> {
		if (item.sourceType === 'youtube') {
			isSeekable = true;
			return { source: createPlaybackSource('youtube'), loadUrl: item.streamUrl };
		}

		if (item.sourceType === 'local') {
			isSeekable = true;
			const loadUrl = item.streamUrl ?? API.stream.local(item.trackSourceId);
			return {
				source: createPlaybackSource('local', { url: loadUrl, seekable: true }),
				loadUrl,
			};
		}

		const response = await fetch(API.stream.jellyfin(item.trackSourceId));
		if (!response.ok) {
			throw new Error(`Failed to resolve Jellyfin playback URL: ${response.status}`);
		}

		const payload: JellyfinPlaybackUrlResponse = await response.json();
		const updatedQueue = [...queue];
		updatedQueue[index] = {
			...item,
			playSessionId: payload.playSessionId,
		};
		queue = updatedQueue;
		isSeekable = payload.seekable;

		return {
			source: createPlaybackSource('jellyfin', { url: payload.url, seekable: payload.seekable }),
			loadUrl: payload.url,
		};
	}

	async function startJellyfinPlaybackSession(index: number): Promise<void> {
		const item = queue[index];
		if (!item || item.sourceType !== 'jellyfin') return;

		try {
			const playSessionId = await startJellyfinSession(item.trackSourceId, item.playSessionId);
			const updatedQueue = [...queue];
			updatedQueue[index] = { ...updatedQueue[index], playSessionId };
			queue = updatedQueue;
			registerBeforeUnloadStop();
		} catch {
			const updatedQueue = [...queue];
			updatedQueue[index] = { ...updatedQueue[index], playSessionId: '' };
			queue = updatedQueue;
		}
	}

	async function loadQueueItem(index: number): Promise<void> {
		const item = queue[index];
		if (!item) return;

		if (errorSkipTimeout) {
			clearTimeout(errorSkipTimeout);
			errorSkipTimeout = null;
		}

		const previousProgress = progress;
		const previousItem = queue[currentIndex] ?? null;
		currentIndex = index;
		playbackState = 'loading';
		progress = 0;
		duration = 0;
		await stopJellyfinSession(previousItem, previousProgress);
		currentSource?.destroy();

		const gen = ++loadGeneration;

		let source: PlaybackSource;
		let resolvedLoadUrl: string | undefined = item.streamUrl;
		try {
			const resolved = await resolveSourceForItem(item, index);
			source = resolved.source;
			resolvedLoadUrl = resolved.loadUrl;
		} catch {
			if (gen === loadGeneration) handleTrackError(gen);
			return;
		}

		currentSource = source;

		const resolvedItem = queue[index] ?? item;
		const metadata: NowPlaying = {
			albumId: resolvedItem.albumId,
			albumName: resolvedItem.albumName,
			artistName: resolvedItem.artistName,
			coverUrl: resolvedItem.coverUrl,
			sourceType: resolvedItem.sourceType,
			trackSourceId: resolvedItem.trackSourceId,
			trackName: resolvedItem.trackName,
			artistId: resolvedItem.artistId,
			streamUrl: resolvedItem.streamUrl,
			format: resolvedItem.format,
		};
		nowPlaying = metadata;
		persistSession();
		subscribeToSource(source, gen);
		source.setVolume(volume);

		try {
			if (resolvedItem.sourceType === 'jellyfin') {
				await startJellyfinPlaybackSession(index);
			}

			await source.load({
				trackSourceId: resolvedItem.trackSourceId,
				url: resolvedLoadUrl,
				format: resolvedItem.format,
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
		if (!nextItem) return;
		if (nextItem.sourceType === 'youtube') return;

		if (nextItem.sourceType === 'jellyfin') {
			void fetch(API.stream.jellyfin(nextItem.trackSourceId), { method: 'HEAD' }).catch(() => {});
			return;
		}

		if (!nextItem.streamUrl) return;
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
				const current = getCurrentJellyfinItem();
				if (current) {
					startJellyfinProgressReportingFor(current);
				}
				prefetchNextTrack();
			}
			if (state === 'paused') {
				const current = getCurrentJellyfinItem();
				if (current?.playSessionId) {
					void reportJellyfinProgress(current.trackSourceId, current.playSessionId, progress, true);
				}
			}
			if (state === 'ended') {
				const current = getCurrentJellyfinItem();
				void stopJellyfinSession(current, progress);

				const nextIdx = getNextIndex();
				if (nextIdx !== null) {
					void loadQueueItem(nextIdx).then(() => {
						cleanupPlayedTracks();
					});
				} else {
					isPlayerVisible = false;
					source.destroy();
					currentSource = null;
					nowPlaying = null;
					playbackState = 'idle';
					isSeekable = true;
					progress = 0;
					duration = 0;
					queue = [];
					currentIndex = 0;
					shuffleOrder = [];
					clearJellyfinProgressReporting();
					unregisterBeforeUnloadStop();
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
		get isSeekable() {
			return isSeekable;
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
			void stopJellyfinSession(getCurrentJellyfinItem(), progress);
			currentSource?.destroy();
			const gen = ++loadGeneration;
			currentSource = source;
			nowPlaying = metadata;
			playbackState = 'loading';
			isSeekable = true;
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
			queue = stampOrigin(items, 'context');
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
				void loadQueueItem(nextIdx).then(() => {
					cleanupPlayedTracks();
				});
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
				const allIndices = Array.from({ length: queue.length }, (_, i) => i);
				const upcoming = allIndices.filter((i) => i !== currentIndex && i > currentIndex);
				const played = allIndices.filter((i) => i < currentIndex);

				for (let i = upcoming.length - 1; i > 0; i--) {
					const j = Math.floor(Math.random() * (i + 1));
					[upcoming[i], upcoming[j]] = [upcoming[j], upcoming[i]];
				}

				shuffleOrder = [...played, currentIndex, ...upcoming];
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
				this.playQueue([stampSingleOrigin(item, 'manual')], 0, false);
				showQueueMutationToast('queue', 1);
				return;
			}

			queue = [...queue, stampSingleOrigin(item, 'manual')];
			if (shuffleEnabled) {
				shuffleOrder = [...shuffleOrder, queue.length - 1];
			}
			persistSession();
			showQueueMutationToast('queue', 1);
		},

		addMultipleToQueue(items: QueueItem[]): void {
			if (items.length === 0) return;

			const stamped = stampOrigin(items, 'manual');
			if (queue.length === 0) {
				this.playQueue(stamped, 0, false);
				showQueueMutationToast('queue', items.length);
				return;
			}

			const startIdx = queue.length;
			queue = [...queue, ...stamped];
			if (shuffleEnabled) {
				const newIndices = items.map((_, i) => startIdx + i);
				shuffleOrder = [...shuffleOrder, ...newIndices];
			}
			persistSession();
			showQueueMutationToast('queue', items.length);
		},

		playNext(item: QueueItem): void {
			if (queue.length === 0) {
				this.playQueue([stampSingleOrigin(item, 'manual')], 0, false);
				showQueueMutationToast('next', 1);
				return;
			}

			const insertAt = currentIndex + 1;
			const newQueue = [...queue];
			newQueue.splice(insertAt, 0, stampSingleOrigin(item, 'manual'));
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

			const stamped = stampOrigin(items, 'manual');
			if (queue.length === 0) {
				this.playQueue(stamped, 0, false);
				showQueueMutationToast('next', items.length);
				return;
			}

			const insertAt = currentIndex + 1;
			const newQueue = [...queue];
			newQueue.splice(insertAt, 0, ...stamped);
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
			if (newSourceType === 'local') {
				streamUrl = API.stream.local(item.trackSourceId);
			} else if (newSourceType === 'jellyfin') {
				streamUrl = API.stream.jellyfin(item.trackSourceId);
			}

			const newQueue = [...queue];
			newQueue[index] = { ...item, sourceType: newSourceType, streamUrl, playSessionId: undefined };
			queue = newQueue;
			persistSession();
		},

		play(): void {
			currentSource?.play();
		},

		pause(): void {
			currentSource?.pause();
			const current = getCurrentJellyfinItem();
			if (current?.playSessionId) {
				void reportJellyfinProgress(current.trackSourceId, current.playSessionId, progress, true);
			}
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
			void stopJellyfinSession(getCurrentJellyfinItem(), progress);
			if (errorSkipTimeout) {
				clearTimeout(errorSkipTimeout);
				errorSkipTimeout = null;
			}
			loadGeneration++;
			currentSource?.destroy();
			currentSource = null;
			nowPlaying = null;
			playbackState = 'idle';
			isSeekable = true;
			isPlayerVisible = false;
			progress = 0;
			duration = 0;
			queue = [];
			currentIndex = 0;
			shuffleOrder = [];
			shuffleEnabled = false;
			consecutiveErrors = 0;
			clearJellyfinProgressReporting();
			unregisterBeforeUnloadStop();
			storeSessionData(null);
		},

		restoreSession(): StoredSession | null {
			return getStoredSession();
		},

		resumeSession(): void {
			const session = getStoredSession();
			if (!session) return;

			const migratedNowPlaying = {
				...session.nowPlaying,
				sourceType: normalizeSourceType(session.nowPlaying.sourceType as SourceType | 'howler'),
			};
			const migratedQueue = session.queue.map((item) => migrateLegacyItem(item as QueueItem & { sourceType: SourceType | 'howler' }));
			const migratedOrder = session.shuffleOrder;
			const migratedCurrentIndex = session.currentIndex;
			const storedProgress = session.progress;
			const storedShuffle = session.shuffleEnabled;

			const stored = migratedNowPlaying;
			const storedQueue = migratedQueue;
			const storedIndex = migratedCurrentIndex;
			const storedOrder = migratedOrder;

			if (stored.sourceType === 'youtube') return;
			if (!storedQueue.length) return;

			queue = storedQueue;
			shuffleEnabled = storedShuffle;
			shuffleOrder = storedOrder;
			isPlayerVisible = true;
			consecutiveErrors = 0;

			const item = storedQueue[storedIndex];
			if (!item) return;

			void stopJellyfinSession(getCurrentJellyfinItem(), progress);
			currentSource?.destroy();
			currentIndex = storedIndex;
			playbackState = 'loading';
			isSeekable = true;
			progress = 0;
			duration = 0;

			const gen = ++loadGeneration;

			void resolveSourceForItem(item, storedIndex).then(async ({ source, loadUrl }) => {
				if (gen !== loadGeneration) return;
				currentSource = source;
				nowPlaying = stored;
				subscribeToSource(source, gen);
				source.setVolume(volume);

				if (item.sourceType === 'jellyfin') {
					await startJellyfinPlaybackSession(storedIndex);
				}

				await source.load({
					trackSourceId: item.trackSourceId,
					url: loadUrl,
					format: item.format,
				});

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
