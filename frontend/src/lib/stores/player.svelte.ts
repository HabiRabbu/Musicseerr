import type { PlaybackSource, PlaybackState, NowPlaying } from '$lib/player/types';

const VOLUME_STORAGE_KEY = 'musicseerr_player_volume';
const SESSION_STORAGE_KEY = 'musicseerr_player_session';

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

function createPlayerStore() {
	let currentSource = $state<PlaybackSource | null>(null);
	let nowPlaying = $state<NowPlaying | null>(null);
	let playbackState = $state<PlaybackState>('idle');
	let volume = $state(getStoredVolume());
	let progress = $state(0);
	let duration = $state(0);
	let isPlayerVisible = $state(false);

	const isPlaying = $derived(playbackState === 'playing');
	const isBuffering = $derived(playbackState === 'buffering' || playbackState === 'loading');

	function subscribeToSource(source: PlaybackSource): void {
		source.onStateChange((state) => {
			playbackState = state;
			if (state === 'ended') {
				isPlayerVisible = false;
				source.destroy();
				currentSource = null;
				nowPlaying = null;
				playbackState = 'idle';
				progress = 0;
				duration = 0;
				storeSession(null);
			}
		});

		source.onProgress((currentTime, totalDuration) => {
			progress = currentTime;
			duration = totalDuration;
		});

		source.onError(() => {
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

		playAlbum(source: PlaybackSource, metadata: NowPlaying): void {
			currentSource?.destroy();
			currentSource = source;
			nowPlaying = metadata;
			playbackState = 'loading';
			isPlayerVisible = true;
			subscribeToSource(source);
			source.setVolume(volume);
			storeSession(metadata);
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
			storeSession(null);
		},

		restoreSession(): NowPlaying | null {
			return getStoredSession();
		}
	};
}

export const playerStore = createPlayerStore();
