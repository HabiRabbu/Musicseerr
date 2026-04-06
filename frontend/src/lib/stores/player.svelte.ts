import type {
	PlaybackSource,
	PlaybackState,
	NowPlaying,
	QueueItem,
	SourceType
} from '$lib/player/types';
import { createPlaybackSource } from '$lib/player/createSource';
import { API } from '$lib/constants';
import { api } from '$lib/api/client';
import {
	reportProgress as reportJellyfinProgress,
	reportStop as reportJellyfinStop,
	startSession as startJellyfinSession
} from '$lib/player/jellyfinPlaybackApi';
import {
	reportNavidromeScrobble,
	reportNavidromeNowPlaying
} from '$lib/player/navidromePlaybackApi';
import { playbackToast } from '$lib/stores/playbackToast.svelte';
import {
	getStoredVolume,
	storeVolume,
	storeSessionData,
	stampOrigin,
	stampSingleOrigin,
	showQueueMutationToast,
	type StoredSession
} from './playerUtils';
import { createProgressReporter, createBeforeUnloadHandler } from './playerJellyfinReporting';
import {
	computeNextIndex,
	computePreviousIndex,
	computeUpcomingLength,
	performCleanup
} from './playerQueueOps';
import {
	resolveSourceUrl,
	buildPrefetchUrl,
	buildNowPlayingMetadata
} from './playerSourceResolver';
import {
	persistSession as doPersistSession,
	restoreSessionData,
	buildResumeState
} from './playerSessionManager';
import {
	addItemToQueue,
	addMultipleItems,
	insertPlayNext,
	insertMultipleNext,
	removeAtIndex,
	performReorder,
	performShuffleReorder,
	clearQueueKeepCurrent
} from './playerQueueMethods';
import {
	buildPlayQueueState,
	computeToggleShuffle,
	changeItemSource,
	updateItemByPlaylistTrackId
} from './playerPlaybackMethods';

const MAX_CONSECUTIVE_ERRORS = 3;
const ERROR_SKIP_DELAY_MS = 2000;
const MAX_HISTORY_LENGTH = 3;
const SESSION_PERSIST_INTERVAL_MS = 5000;
const JELLYFIN_REPORT_INTERVAL_MS = 10_000;
const MAX_JELLYFIN_REPORT_FAILURES = 3;

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
	let beforeUnloadRegistered = false;

	const isPlaying = $derived(playbackState === 'playing');
	const isBuffering = $derived(playbackState === 'buffering' || playbackState === 'loading');
	const hasQueue = $derived(queue.length > 0);
	const hasNext = $derived.by(() => {
		if (queue.length <= 1) return false;
		if (shuffleEnabled) {
			const si = shuffleOrder.indexOf(currentIndex);
			return si < shuffleOrder.length - 1;
		}
		return currentIndex < queue.length - 1;
	});
	const hasPrevious = $derived.by(() => {
		if (queue.length <= 1) return false;
		if (shuffleEnabled) {
			const si = shuffleOrder.indexOf(currentIndex);
			return si > 0;
		}
		return currentIndex > 0;
	});
	const currentQueueItem = $derived(queue.length > 0 ? queue[currentIndex] : null);
	const queueLength = $derived(queue.length);
	const currentTrackNumber = $derived(currentIndex + 1);

	const progressReporter = createProgressReporter(
		reportJellyfinProgress,
		JELLYFIN_REPORT_INTERVAL_MS,
		MAX_JELLYFIN_REPORT_FAILURES
	);
	const handleBeforeUnload = createBeforeUnloadHandler(
		() => ({ jellyfinItem: getJellyfinItem(), currentItem: queue[currentIndex] ?? null, progress }),
		API.stream.jellyfinStop,
		API.stream.navidromeScrobble
	);

	function getNextIndex(): number | null {
		return computeNextIndex(currentIndex, queue.length, shuffleEnabled, shuffleOrder);
	}
	function getPreviousIndex(): number | null {
		return computePreviousIndex(currentIndex, queue.length, shuffleEnabled, shuffleOrder);
	}
	function getJellyfinItem(): QueueItem | null {
		const item = queue[currentIndex];
		return item?.sourceType === 'jellyfin' ? item : null;
	}
	function persist(): void {
		doPersistSession(nowPlaying, queue, currentIndex, progress, shuffleEnabled, shuffleOrder);
	}

	function registerBeforeUnload(): void {
		if (beforeUnloadRegistered || typeof window === 'undefined') return;
		window.addEventListener('beforeunload', handleBeforeUnload);
		beforeUnloadRegistered = true;
	}
	function unregisterBeforeUnload(): void {
		if (!beforeUnloadRegistered || typeof window === 'undefined') return;
		window.removeEventListener('beforeunload', handleBeforeUnload);
		beforeUnloadRegistered = false;
	}
	async function stopJellyfinSession(item: QueueItem | null, posSeconds: number): Promise<void> {
		progressReporter.stop();
		unregisterBeforeUnload();
		if (!item || item.sourceType !== 'jellyfin' || !item.playSessionId) return;
		await reportJellyfinStop(item.trackSourceId, item.playSessionId, posSeconds);
	}

	function applyResetState(): void {
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
		progressReporter.stop();
		unregisterBeforeUnload();
		storeSessionData(null);
	}

	async function resolveSourceForItem(
		item: QueueItem
	): Promise<{ source: PlaybackSource; loadUrl: string | undefined }> {
		const url = resolveSourceUrl(item);
		if (item.sourceType === 'youtube') {
			isSeekable = true;
			return { source: createPlaybackSource('youtube'), loadUrl: url };
		}
		if (item.sourceType === 'local') {
			isSeekable = true;
			return { source: createPlaybackSource('local', { url: url!, seekable: true }), loadUrl: url };
		}
		if (item.sourceType === 'navidrome') {
			isSeekable = true;
			void reportNavidromeNowPlaying(item.trackSourceId);
			return {
				source: createPlaybackSource('navidrome', { url: url!, seekable: true }),
				loadUrl: url
			};
		}
		isSeekable = true;
		return {
			source: createPlaybackSource('jellyfin', { url: url!, seekable: true }),
			loadUrl: url
		};
	}

	async function startJellyfinPlayback(index: number): Promise<void> {
		const item = queue[index];
		if (!item || item.sourceType !== 'jellyfin') return;
		try {
			const playSessionId = await startJellyfinSession(item.trackSourceId, item.playSessionId);
			const uq = [...queue];
			uq[index] = { ...uq[index], playSessionId };
			queue = uq;
			registerBeforeUnload();
		} catch {
			const uq = [...queue];
			uq[index] = { ...uq[index], playSessionId: '' };
			queue = uq;
		}
	}

	async function loadQueueItem(index: number): Promise<void> {
		const item = queue[index];
		if (!item) return;
		if (errorSkipTimeout) {
			clearTimeout(errorSkipTimeout);
			errorSkipTimeout = null;
		}
		const prevProgress = progress,
			prevItem = queue[currentIndex] ?? null;
		currentIndex = index;
		playbackState = 'loading';
		progress = 0;
		duration = 0;
		await stopJellyfinSession(prevItem, prevProgress);
		currentSource?.destroy();
		const gen = ++loadGeneration;
		let source: PlaybackSource,
			resolvedUrl: string | undefined = item.streamUrl;
		try {
			const r = await resolveSourceForItem(item);
			source = r.source;
			resolvedUrl = r.loadUrl;
		} catch {
			if (gen === loadGeneration) handleTrackError(gen);
			return;
		}
		currentSource = source;
		nowPlaying = buildNowPlayingMetadata(queue[index] ?? item);
		persist();
		subscribeToSource(source, gen);
		source.setVolume(volume);
		try {
			if ((queue[index] ?? item).sourceType === 'jellyfin') await startJellyfinPlayback(index);
			await source.load({
				trackSourceId: (queue[index] ?? item).trackSourceId,
				url: resolvedUrl,
				format: (queue[index] ?? item).format
			});
			if (gen === loadGeneration) source.play();
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
			playbackToast.show('Multiple tracks failed — playback stopped', 'error');
			applyResetState();
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

	function prefetchNext(): void {
		const nextIdx = getNextIndex();
		if (nextIdx === null) return;
		const nextItem = queue[nextIdx];
		if (!nextItem) return;
		const url = buildPrefetchUrl(nextItem);
		if (url) void api.global.head(url).catch(() => {});
	}

	function subscribeToSource(source: PlaybackSource, gen: number): void {
		source.onStateChange((state) => {
			if (gen !== loadGeneration) return;
			playbackState = state;
			if (state === 'playing') {
				consecutiveErrors = 0;
				if (getJellyfinItem())
					progressReporter.start(() => ({
						jellyfinItem: getJellyfinItem(),
						progress,
						isPaused: playbackState !== 'playing'
					}));
				prefetchNext();
			}
			if (state === 'paused') {
				const jf = getJellyfinItem();
				if (jf?.playSessionId)
					void reportJellyfinProgress(jf.trackSourceId, jf.playSessionId, progress, true);
			}
			if (state === 'ended') {
				const ci = queue[currentIndex] ?? null;
				void stopJellyfinSession(getJellyfinItem(), progress);
				if (ci?.sourceType === 'navidrome') void reportNavidromeScrobble(ci.trackSourceId);
				const nextIdx = getNextIndex();
				if (nextIdx !== null) {
					void loadQueueItem(nextIdx).then(() => {
						const c = performCleanup(
							queue,
							currentIndex,
							shuffleEnabled,
							shuffleOrder,
							MAX_HISTORY_LENGTH
						);
						queue = c.newQueue;
						currentIndex = c.newIndex;
						shuffleOrder = c.newShuffleOrder;
						persist();
					});
				} else {
					applyResetState();
				}
			}
		});
		source.onProgress((t, d) => {
			if (gen !== loadGeneration) return;
			progress = t;
			duration = d;
			const now = Date.now();
			if (now - lastPersistTime >= SESSION_PERSIST_INTERVAL_MS) {
				lastPersistTime = now;
				persist();
			}
		});
		source.onError(() => {
			if (gen !== loadGeneration) return;
			handleTrackError(gen);
		});
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
			return computeUpcomingLength(queue.length, currentIndex, shuffleEnabled, shuffleOrder);
		},
		get currentTrackNumber() {
			return currentTrackNumber;
		},
		get shuffleOrder() {
			return shuffleOrder;
		},

		playAlbum(source: PlaybackSource, metadata: NowPlaying): void {
			void stopJellyfinSession(getJellyfinItem(), progress);
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
			persist();
		},

		playQueue(items: QueueItem[], startIndex: number = 0, shuffle: boolean = false): void {
			if (items.length === 0) return;
			const s = buildPlayQueueState(items, startIndex, shuffle);
			queue = s.queue;
			shuffleEnabled = s.shuffleEnabled;
			shuffleOrder = s.shuffleOrder;
			isPlayerVisible = s.isPlayerVisible;
			consecutiveErrors = 0;
			void loadQueueItem(s.startIndex);
		},

		nextTrack(): void {
			const idx = getNextIndex();
			if (idx !== null)
				void loadQueueItem(idx).then(() => {
					const c = performCleanup(
						queue,
						currentIndex,
						shuffleEnabled,
						shuffleOrder,
						MAX_HISTORY_LENGTH
					);
					queue = c.newQueue;
					currentIndex = c.newIndex;
					shuffleOrder = c.newShuffleOrder;
					persist();
				});
		},

		previousTrack(): void {
			const idx = getPreviousIndex();
			if (idx !== null) void loadQueueItem(idx);
		},

		toggleShuffle(): void {
			const r = computeToggleShuffle(queue.length, currentIndex, shuffleEnabled);
			shuffleEnabled = r.shuffleEnabled;
			shuffleOrder = r.shuffleOrder;
		},

		jumpToTrack(index: number): void {
			if (index >= 0 && index < queue.length) void loadQueueItem(index);
		},

		addToQueue(item: QueueItem): void {
			if (queue.length === 0) {
				this.playQueue([stampSingleOrigin(item, 'manual')], 0, false);
				showQueueMutationToast('queue', 1);
				return;
			}
			const r = addItemToQueue(queue, item, shuffleEnabled, shuffleOrder);
			queue = r.newQueue;
			shuffleOrder = r.newShuffleOrder;
			persist();
			showQueueMutationToast('queue', 1);
		},

		addMultipleToQueue(items: QueueItem[]): void {
			if (items.length === 0) return;
			if (queue.length === 0) {
				this.playQueue(stampOrigin(items, 'manual'), 0, false);
				showQueueMutationToast('queue', items.length);
				return;
			}
			const r = addMultipleItems(queue, items, shuffleEnabled, shuffleOrder);
			queue = r.newQueue;
			shuffleOrder = r.newShuffleOrder;
			persist();
			showQueueMutationToast('queue', items.length);
		},

		playNext(item: QueueItem): void {
			if (queue.length === 0) {
				this.playQueue([stampSingleOrigin(item, 'manual')], 0, false);
				showQueueMutationToast('next', 1);
				return;
			}
			const r = insertPlayNext(queue, item, currentIndex, shuffleEnabled, shuffleOrder);
			queue = r.newQueue;
			shuffleOrder = r.newShuffleOrder;
			persist();
			showQueueMutationToast('next', 1);
		},

		playMultipleNext(items: QueueItem[]): void {
			if (items.length === 0) return;
			if (queue.length === 0) {
				this.playQueue(stampOrigin(items, 'manual'), 0, false);
				showQueueMutationToast('next', items.length);
				return;
			}
			const r = insertMultipleNext(queue, items, currentIndex, shuffleEnabled, shuffleOrder);
			queue = r.newQueue;
			shuffleOrder = r.newShuffleOrder;
			persist();
			showQueueMutationToast('next', items.length);
		},

		removeFromQueue(index: number): void {
			if (index < 0 || index >= queue.length) return;
			if (queue.length <= 1) {
				this.stop();
				return;
			}
			const r = removeAtIndex(queue, index, currentIndex, shuffleEnabled, shuffleOrder);
			queue = r.newQueue;
			currentIndex = r.newIndex;
			shuffleOrder = r.newShuffleOrder;
			if (r.wasPlaying) {
				void loadQueueItem(r.newIndex);
			} else {
				persist();
			}
		},

		reorderQueue(fromIndex: number, toIndex: number): void {
			const r = performReorder(queue, fromIndex, toIndex, currentIndex);
			queue = r.newQueue;
			currentIndex = r.newCurrentIndex;
			persist();
		},

		reorderShuffleOrder(fromPos: number, toPos: number): void {
			shuffleOrder = performShuffleReorder(shuffleOrder, fromPos, toPos);
			persist();
		},

		clearQueue(): void {
			if (queue.length === 0 || !queue[currentIndex]) {
				this.stop();
				return;
			}
			const r = clearQueueKeepCurrent(queue, currentIndex);
			queue = r.newQueue;
			currentIndex = r.newIndex;
			shuffleEnabled = false;
			shuffleOrder = [];
			persist();
		},

		changeTrackSource(index: number, newSourceType: SourceType): void {
			if (index < 0 || index >= queue.length) return;
			if (index === currentIndex) {
				playbackToast.show('Cannot change source for the currently playing track', 'warning');
				return;
			}
			const r = changeItemSource(queue, index, newSourceType);
			if (r.error) {
				playbackToast.show(r.error, 'warning');
				return;
			}
			queue = r.newQueue;
			persist();
		},

		updateQueueItemByPlaylistTrackId(
			playlistTrackId: string,
			newSourceType: SourceType,
			newTrackSourceId: string,
			newFormat?: string
		): void {
			const r = updateItemByPlaylistTrackId(
				queue,
				playlistTrackId,
				currentIndex,
				newSourceType,
				newTrackSourceId,
				newFormat
			);
			if (r) {
				queue = r;
				persist();
			}
		},

		play(): void {
			currentSource?.play();
		},

		pause(): void {
			currentSource?.pause();
			const jf = getJellyfinItem();
			if (jf?.playSessionId)
				void reportJellyfinProgress(jf.trackSourceId, jf.playSessionId, progress, true);
			persist();
		},

		togglePlay(): void {
			if (isPlaying) currentSource?.pause();
			else currentSource?.play();
		},
		seekTo(seconds: number): void {
			currentSource?.seekTo(seconds);
			progress = seconds;
			persist();
		},

		setVolume(level: number): void {
			const clamped = Math.max(0, Math.min(100, level));
			volume = clamped;
			currentSource?.setVolume(clamped);
			storeVolume(clamped);
		},

		stop(): void {
			void stopJellyfinSession(getJellyfinItem(), progress);
			if (errorSkipTimeout) {
				clearTimeout(errorSkipTimeout);
				errorSkipTimeout = null;
			}
			loadGeneration++;
			applyResetState();
		},

		restoreSession(): StoredSession | null {
			return restoreSessionData();
		},

		resumeSession(): void {
			const session = restoreSessionData();
			if (!session) return;
			const resume = buildResumeState(session);
			if (!resume) return;

			queue = resume.queue;
			shuffleEnabled = resume.shuffleEnabled;
			shuffleOrder = resume.shuffleOrder;
			isPlayerVisible = true;
			consecutiveErrors = 0;
			void stopJellyfinSession(getJellyfinItem(), progress);
			currentSource?.destroy();
			currentIndex = resume.currentIndex;
			playbackState = 'loading';
			isSeekable = true;
			progress = 0;
			duration = 0;
			const gen = ++loadGeneration;

			void resolveSourceForItem(resume.currentItem)
				.then(async ({ source, loadUrl }) => {
					if (gen !== loadGeneration) return;
					currentSource = source;
					nowPlaying = resume.nowPlaying;
					subscribeToSource(source, gen);
					source.setVolume(volume);
					if (resume.currentItem.sourceType === 'jellyfin') {
						await startJellyfinPlayback(resume.currentIndex);
					}
					await source.load({
						trackSourceId: resume.currentItem.trackSourceId,
						url: loadUrl,
						format: resume.currentItem.format
					});
					if (gen !== loadGeneration) return;
					playbackState = 'paused';
					duration = source.getDuration();
					if (resume.progress > 0) {
						source.seekTo(resume.progress);
						progress = resume.progress;
					}
				})
				.catch(() => {
					if (gen === loadGeneration) {
						playbackState = 'error';
						storeSessionData(null);
					}
				});
		}
	};
}

export const playerStore = createPlayerStore();
