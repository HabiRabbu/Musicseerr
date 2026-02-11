import type { PlaybackSource, PlaybackState, NowPlaying, QueueItem } from '$lib/player/types';
import { YouTubePlaybackSource } from '$lib/player/YouTubePlaybackSource';

const VOLUME_STORAGE_KEY = 'musicseerr_player_volume';
const SESSION_STORAGE_KEY = 'musicseerr_player_session';
const PLAYER_ELEMENT_ID = 'yt-player-embed';

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

function getStoredSession(): NowPlaying | null {
	try {
		const stored = localStorage.getItem(SESSION_STORAGE_KEY);
		if (stored) return JSON.parse(stored);
	} catch {}
	return null;
}

function storeSession(nowPlaying: NowPlaying | null): void {
	try {
		if (nowPlaying) {
			localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(nowPlaying));
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

	const isPlaying = $derived(playbackState === 'playing');
	const isBuffering = $derived(playbackState === 'buffering' || playbackState === 'loading');
	const hasQueue = $derived(queue.length > 1);

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

		currentSource?.destroy();
		currentIndex = index;
		playbackState = 'loading';
		progress = 0;
		duration = 0;

		const gen = ++loadGeneration;
		const source = new YouTubePlaybackSource(PLAYER_ELEMENT_ID);
		currentSource = source;

		const metadata: NowPlaying = {
			albumId: item.albumId,
			albumName: item.albumName,
			artistName: item.artistName,
			coverUrl: item.coverUrl,
			sourceType: item.sourceType,
			videoId: item.videoId,
			trackName: item.trackName,
			artistId: item.artistId,
		};
		nowPlaying = metadata;
		storeSession(metadata);
		subscribeToSource(source, gen);
		source.setVolume(volume);

		try {
			await source.load({ videoId: item.videoId });
		} catch {
			if (gen === loadGeneration) playbackState = 'error';
		}
	}

	function subscribeToSource(source: PlaybackSource, gen: number): void {
		source.onStateChange((state) => {
			if (gen !== loadGeneration) return;
			playbackState = state;
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
					storeSession(null);
				}
			}
		});

		source.onProgress((currentTime, totalDuration) => {
			if (gen !== loadGeneration) return;
			progress = currentTime;
			duration = totalDuration;
		});

		source.onError(() => {
			if (gen !== loadGeneration) return;
			playbackState = 'error';
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
		get currentTrackNumber() {
			return currentTrackNumber;
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
			subscribeToSource(source, gen);
			source.setVolume(volume);
			storeSession(metadata);
		},

		playQueue(items: QueueItem[], startIndex: number = 0, shuffle: boolean = false): void {
			if (items.length === 0) return;
			queue = items;
			shuffleEnabled = shuffle;
			isPlayerVisible = true;

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

		play(): void {
			currentSource?.play();
		},

		pause(): void {
			currentSource?.pause();
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
		},

		setVolume(level: number): void {
			const clamped = Math.max(0, Math.min(100, level));
			volume = clamped;
			currentSource?.setVolume(clamped);
			storeVolume(clamped);
		},

		stop(): void {
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
			storeSession(null);
		},

		restoreSession(): NowPlaying | null {
			return getStoredSession();
		}
	};
}

export const playerStore = createPlayerStore();
