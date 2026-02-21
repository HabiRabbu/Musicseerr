import type { Howl as HowlType } from 'howler';
import type { PlaybackSource, PlaybackState, SourceType } from './types';

let HowlConstructor: typeof HowlType | null = null;
let howlerLoadPromise: Promise<typeof HowlType> | null = null;

async function getHowlConstructor(): Promise<typeof HowlType> {
	if (HowlConstructor) return HowlConstructor;
	if (!howlerLoadPromise) {
		howlerLoadPromise = import('howler').then((m) => {
			HowlConstructor = m.Howl;
			return m.Howl;
		});
	}
	return howlerLoadPromise;
}

const MEDIA_ERROR_MESSAGES: Record<number, string> = {
	1: 'Playback aborted',
	2: 'Network error — connection lost',
	3: 'Audio format not supported by browser',
	4: 'Audio format not supported by browser',
};

const STALL_TIMEOUT_MS = 15_000;

export abstract class HowlerPlaybackBase implements PlaybackSource {
	abstract readonly type: SourceType;

	private static readonly LOAD_TIMEOUT_MS = 15_000;

	protected howl: HowlType | null = null;
	private progressInterval: ReturnType<typeof setInterval> | null = null;
	private loadTimeoutHandle: ReturnType<typeof setTimeout> | null = null;
	private stallTimeoutHandle: ReturnType<typeof setTimeout> | null = null;
	private nativeListeners: { event: string; handler: EventListener }[] = [];
	private stateCallbacks: ((state: PlaybackState) => void)[] = [];
	private readyCallbacks: (() => void)[] = [];
	private errorCallbacks: ((error: { code: string; message: string }) => void)[] = [];
	private progressCallbacks: ((currentTime: number, duration: number) => void)[] = [];
	private destroyed = false;
	private pendingVolume = 75;
	private isPlaying = false;

	protected onBeforeLoad(_info: {
		videoId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> | void {}

	protected onAfterLoad(): void {}

	protected onDestroy(): void {}

	async load(info: {
		videoId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> {
		if (!info.url) throw new Error('url is required for Howler-based playback source');

		this.stateCallbacks.forEach((cb) => cb('loading'));

		await this.onBeforeLoad(info);
		if (this.destroyed) return;

		const format = info.format ?? 'aac';

		const Howl = await getHowlConstructor();
		if (this.destroyed) return;

		await new Promise<void>((resolve, reject) => {
			let settled = false;
			this.loadTimeoutHandle = setTimeout(() => {
				if (settled) return;
				settled = true;
				this.loadTimeoutHandle = null;
				const err = { code: 'LOAD_TIMEOUT', message: 'Audio load timed out' };
				reject(err);
			}, HowlerPlaybackBase.LOAD_TIMEOUT_MS);

			const settle = (fn: () => void) => {
				if (settled) return;
				settled = true;
				if (this.loadTimeoutHandle) {
					clearTimeout(this.loadTimeoutHandle);
					this.loadTimeoutHandle = null;
				}
				fn();
			};

			this.howl = new Howl({
				src: [info.url!],
				html5: true,
				format: [format],
				volume: this.pendingVolume / 100
			});

			this.howl.on('load', () => {
				settle(() => {
					if (this.destroyed) {
						resolve();
						return;
					}
					this.readyCallbacks.forEach((cb) => cb());
					this.startProgressPolling();
					this.onAfterLoad();
					resolve();
				});
			});

			this.howl.on('loaderror', (_id: number, error: unknown) => {
				settle(() => {
					if (this.destroyed) {
						resolve();
						return;
					}
					const err = {
						code: 'LOAD_ERROR',
						message: typeof error === 'string' ? error : 'Failed to load audio'
					};
					reject(err);
				});
			});

			this.howl.on('playerror', (_id: number, error: unknown) => {
				if (this.destroyed) return;
				const err = {
					code: 'PLAY_ERROR',
					message: typeof error === 'string' ? error : 'Failed to play audio'
				};
				this.errorCallbacks.forEach((cb) => cb(err));
			});

			this.howl.on('play', () => {
				if (this.destroyed) return;
				this.isPlaying = true;
				this.stateCallbacks.forEach((cb) => cb('playing'));
			});

			this.howl.on('pause', () => {
				if (this.destroyed) return;
				this.isPlaying = false;
				this.stateCallbacks.forEach((cb) => cb('paused'));
			});

			this.howl.on('end', () => {
				if (this.destroyed) return;
				this.isPlaying = false;
				this.stateCallbacks.forEach((cb) => cb('ended'));
			});

			this.howl.on('seek', () => {
				if (this.destroyed) return;
				const state = this.isPlaying ? 'playing' : 'paused';
				this.stateCallbacks.forEach((cb) => cb(state));
			});

			this.attachNativeAudioListeners();
		});
	}

	play(): void {
		this.howl?.play();
	}

	pause(): void {
		this.howl?.pause();
	}

	seekTo(seconds: number): void {
		this.howl?.seek(seconds);
	}

	setVolume(level: number): void {
		this.pendingVolume = Math.max(0, Math.min(100, level));
		this.howl?.volume(this.pendingVolume / 100);
	}

	getCurrentTime(): number {
		if (!this.howl) return 0;
		const pos = this.howl.seek();
		return typeof pos === 'number' ? pos : 0;
	}

	getDuration(): number {
		return this.howl?.duration() ?? 0;
	}

	destroy(): void {
		this.destroyed = true;
		this.onDestroy();
		this.stopProgressPolling();
		this.removeNativeAudioListeners();
		if (this.loadTimeoutHandle) {
			clearTimeout(this.loadTimeoutHandle);
			this.loadTimeoutHandle = null;
		}
		if (this.stallTimeoutHandle) {
			clearTimeout(this.stallTimeoutHandle);
			this.stallTimeoutHandle = null;
		}
		if (this.howl) {
			this.howl.unload();
			this.howl = null;
		}
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

	private getAudioNode(): HTMLAudioElement | null {
		try {
			const sounds = (this.howl as unknown as { _sounds: { _node: HTMLAudioElement }[] })
				?._sounds;
			return sounds?.[0]?._node ?? null;
		} catch {
			return null;
		}
	}

	private attachNativeAudioListeners(): void {
		const node = this.getAudioNode();
		if (!node) return;

		const onStallStart = () => {
			if (this.destroyed || !this.isPlaying) return;
			if (this.stallTimeoutHandle) return;
			this.stateCallbacks.forEach((cb) => cb('loading'));
			this.stallTimeoutHandle = setTimeout(() => {
				this.stallTimeoutHandle = null;
				if (this.destroyed) return;
				const err = { code: 'NETWORK_STALL', message: 'Audio stream stalled — network issue' };
				this.errorCallbacks.forEach((cb) => cb(err));
			}, STALL_TIMEOUT_MS);
		};

		const onStallEnd = () => {
			if (this.stallTimeoutHandle) {
				clearTimeout(this.stallTimeoutHandle);
				this.stallTimeoutHandle = null;
			}
			if (!this.destroyed && this.isPlaying) {
				this.stateCallbacks.forEach((cb) => cb('playing'));
			}
		};

		const onMediaError = () => {
			if (this.destroyed) return;
			const mediaErr = node.error;
			const msg = MEDIA_ERROR_MESSAGES[mediaErr?.code ?? 0] ?? 'Unknown playback error';
			const err = { code: `MEDIA_ERROR_${mediaErr?.code ?? 0}`, message: msg };
			this.errorCallbacks.forEach((cb) => cb(err));
		};

		node.addEventListener('waiting', onStallStart);
		node.addEventListener('stalled', onStallStart);
		node.addEventListener('playing', onStallEnd);
		node.addEventListener('error', onMediaError);

		this.nativeListeners = [
			{ event: 'waiting', handler: onStallStart },
			{ event: 'stalled', handler: onStallStart },
			{ event: 'playing', handler: onStallEnd },
			{ event: 'error', handler: onMediaError },
		];
	}

	private removeNativeAudioListeners(): void {
		const node = this.getAudioNode();
		if (node) {
			for (const { event, handler } of this.nativeListeners) {
				node.removeEventListener(event, handler);
			}
		}
		this.nativeListeners = [];
	}

	private startProgressPolling(): void {
		this.stopProgressPolling();
		this.progressInterval = setInterval(() => {
			if (this.howl && !this.destroyed) {
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
}
