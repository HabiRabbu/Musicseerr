/* eslint-disable @typescript-eslint/no-namespace */
import type { PlaybackSource, PlaybackState } from './types';

declare global {
	interface Window {
		YT: typeof YT;
		onYouTubeIframeAPIReady: (() => void) | undefined;
	}
}

declare namespace YT {
	class Player {
		constructor(elementId: string, options: PlayerOptions);
		playVideo(): void;
		pauseVideo(): void;
		seekTo(seconds: number, allowSeekAhead: boolean): void;
		setVolume(volume: number): void;
		getCurrentTime(): number;
		getDuration(): number;
		getPlayerState(): number;
		destroy(): void;
	}

	interface PlayerOptions {
		height?: string | number;
		width?: string | number;
		videoId?: string;
		playerVars?: Record<string, number | string>;
		events?: {
			onReady?: (event: { target: Player }) => void;
			onStateChange?: (event: { data: number }) => void;
			onError?: (event: { data: number }) => void;
		};
	}

	enum PlayerState {
		UNSTARTED = -1,
		ENDED = 0,
		PLAYING = 1,
		PAUSED = 2,
		BUFFERING = 3,
		CUED = 5
	}
}

let apiLoaded = false;
let apiLoading = false;
const apiReadyQueue: { resolve: () => void; reject: (err: Error) => void }[] = [];

function flushQueue(error?: Error): void {
	const pending = apiReadyQueue.splice(0);
	for (const { resolve, reject } of pending) {
		if (error) {
			reject(error);
		} else {
			resolve();
		}
	}
}

function loadYouTubeAPI(): Promise<void> {
	if (typeof window !== 'undefined' && window.YT?.Player) {
		apiLoaded = true;
		return Promise.resolve();
	}

	if (apiLoaded) return Promise.resolve();

	return new Promise((resolve, reject) => {
		apiReadyQueue.push({ resolve, reject });
		if (apiLoading) return;

		apiLoading = true;

		const timeout = setTimeout(() => {
			apiLoading = false;
			flushQueue(new Error('YouTube IFrame API failed to load (timeout)'));
		}, 15000);

		const existingCallback = window.onYouTubeIframeAPIReady;
		window.onYouTubeIframeAPIReady = () => {
			clearTimeout(timeout);
			existingCallback?.();
			apiLoaded = true;
			apiLoading = false;
			flushQueue();
		};

		if (!document.querySelector('script[src="https://www.youtube.com/iframe_api"]')) {
			const script = document.createElement('script');
			script.src = 'https://www.youtube.com/iframe_api';
			script.onerror = () => {
				clearTimeout(timeout);
				apiLoading = false;
				flushQueue(new Error('Failed to load YouTube IFrame API script'));
			};
			document.head.appendChild(script);
		}
	});
}

export class YouTubePlaybackSource implements PlaybackSource {
	readonly type = 'youtube' as const;

	private player: YT.Player | null = null;
	private elementId: string;
	private progressInterval: ReturnType<typeof setInterval> | null = null;
	private stateCallbacks: ((state: PlaybackState) => void)[] = [];
	private readyCallbacks: (() => void)[] = [];
	private errorCallbacks: ((error: { code: string; message: string }) => void)[] = [];
	private progressCallbacks: ((currentTime: number, duration: number) => void)[] = [];
	private destroyed = false;
	private pendingVolume = 75;

	constructor(elementId: string) {
		this.elementId = elementId;
	}

	async load(info: {
		trackSourceId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> {
		if (!info.trackSourceId) throw new Error('trackSourceId is required for YouTube source');

		await loadYouTubeAPI();
		if (this.destroyed) return;
		if (!document.getElementById(this.elementId)) {
			throw new Error(`YouTube player mount target not found: ${this.elementId}`);
		}

		return new Promise<void>((resolve, reject) => {
			try {
				this.player = new window.YT.Player(this.elementId, {
					height: '68',
					width: '120',
					videoId: info.trackSourceId,
					playerVars: {
						controls: 0,
						modestbranding: 1,
						rel: 0,
						playsinline: 1,
						autoplay: 1
					},
					events: {
						onReady: () => {
							if (this.destroyed) {
								resolve();
								return;
							}
							this.player?.setVolume(this.pendingVolume);
							this.readyCallbacks.forEach((cb) => cb());
							this.startProgressPolling();
							resolve();
						},
						onStateChange: (event) => {
							const state = this.mapPlayerState(event.data);
							this.stateCallbacks.forEach((cb) => cb(state));
						},
						onError: (event) => {
							const error = this.mapError(event.data);
							this.errorCallbacks.forEach((cb) => cb(error));
							reject(error);
						}
					}
				});
			} catch (e) {
				reject(e);
			}
		});
	}

	play(): void {
		this.player?.playVideo();
	}

	pause(): void {
		this.player?.pauseVideo();
	}

	seekTo(seconds: number): void {
		this.player?.seekTo(seconds, true);
	}

	setVolume(level: number): void {
		this.pendingVolume = Math.max(0, Math.min(100, level));
		this.player?.setVolume(this.pendingVolume);
	}

	getCurrentTime(): number {
		return this.player?.getCurrentTime() ?? 0;
	}

	getDuration(): number {
		return this.player?.getDuration() ?? 0;
	}

	destroy(): void {
		this.destroyed = true;
		this.stopProgressPolling();
		this.player?.destroy();
		this.player = null;
		this.stateCallbacks = [];
		this.readyCallbacks = [];
		this.errorCallbacks = [];
		this.progressCallbacks = [];
	}

	onStateChange(callback: (state: PlaybackState) => void): void {
		this.stateCallbacks.push(callback);
	}

	onReady(callback: () => void): void {
		this.readyCallbacks.push(callback);
	}

	onError(callback: (error: { code: string; message: string }) => void): void {
		this.errorCallbacks.push(callback);
	}

	onProgress(callback: (currentTime: number, duration: number) => void): void {
		this.progressCallbacks.push(callback);
	}

	private startProgressPolling(): void {
		this.stopProgressPolling();
		this.progressInterval = setInterval(() => {
			if (this.player && !this.destroyed) {
				const time = this.getCurrentTime();
				const duration = this.getDuration();
				this.progressCallbacks.forEach((cb) => cb(time, duration));
			}
		}, 500);
	}

	private stopProgressPolling(): void {
		if (this.progressInterval) {
			clearInterval(this.progressInterval);
			this.progressInterval = null;
		}
	}

	private mapPlayerState(ytState: number): PlaybackState {
		switch (ytState) {
			case -1:
				return 'loading';
			case 0:
				return 'ended';
			case 1:
				return 'playing';
			case 2:
				return 'paused';
			case 3:
				return 'buffering';
			case 5:
				return 'loading';
			default:
				return 'idle';
		}
	}

	private mapError(errorCode: number): { code: string; message: string } {
		const errors: Record<number, string> = {
			2: 'Invalid video ID',
			5: 'HTML5 player error',
			100: 'Video not found or removed',
			101: 'Video cannot be embedded',
			150: 'Video cannot be embedded'
		};
		return {
			code: String(errorCode),
			message: errors[errorCode] ?? `YouTube error: ${errorCode}`
		};
	}
}
