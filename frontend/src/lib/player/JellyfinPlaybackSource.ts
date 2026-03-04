import type { SourceType } from './types';
import { HowlerPlaybackBase } from './HowlerPlaybackBase';
import * as jellyfinApi from './jellyfinPlaybackApi';

const PROGRESS_REPORT_INTERVAL_MS = 10_000;
const MAX_REPORT_FAILURES = 3;
const SEEK_DEBOUNCE_MS = 300;

export class JellyfinPlaybackSource extends HowlerPlaybackBase {
	readonly type: SourceType = 'jellyfin';

	private playSessionId: string | null = null;
	private itemId: string | null = null;
	private reportInterval: ReturnType<typeof setInterval> | null = null;
	private isPaused = false;
	private consecutiveReportFailures = 0;
	private sessionHealthy = true;

	private primaryLoadInfo: {
		trackSourceId?: string;
		url?: string;
		token?: string;
		format?: string;
	} | null = null;
	private seekOffset = 0;
	private skipSessionStartOnNextLoad = false;
	private seekDebounceTimer: ReturnType<typeof setTimeout> | null = null;
	private seekLoadGeneration = 0;
	private isDirectPlay = false;

	override async load(info: {
		trackSourceId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> {
		this.seekLoadGeneration++;
		if (this.seekDebounceTimer) {
			clearTimeout(this.seekDebounceTimer);
			this.seekDebounceTimer = null;
		}
		this.primaryLoadInfo = info;
		this.seekOffset = 0;
		return super.load(info);
	}

	override seekTo(seconds: number): void {
		if (this.isDirectPlay) {
			this.seekOffset = 0;
			super.seekTo(seconds);
			return;
		}

		if (!this.primaryLoadInfo?.url) {
			super.seekTo(seconds);
			return;
		}

		this.seekOffset = seconds;
		const generation = ++this.seekLoadGeneration;
		if (this.seekDebounceTimer) {
			clearTimeout(this.seekDebounceTimer);
		}
		this.seekDebounceTimer = setTimeout(() => {
			this.seekDebounceTimer = null;
			void this.reloadFromSeekOffset(seconds, generation);
		}, SEEK_DEBOUNCE_MS);
	}

	override getCurrentTime(): number {
		if (!this.howl) return this.seekOffset;
		const pos = this.howl.seek();
		const currentPos = typeof pos === 'number' ? pos : 0;
		return this.isDirectPlay ? currentPos : this.seekOffset + currentPos;
	}

	protected override async onBeforeLoad(info: {
		trackSourceId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> {
		this.itemId = info.trackSourceId ?? this.extractItemId(info.url);
		if (!this.itemId) return;

		if (this.skipSessionStartOnNextLoad && this.playSessionId) {
			this.skipSessionStartOnNextLoad = false;
			return;
		}

		this.skipSessionStartOnNextLoad = false;

		try {
			this.playSessionId = await jellyfinApi.startSession(this.itemId);
		} catch (err) {
			console.warn('[Jellyfin] session start failed, playback reporting disabled:', err);
			this.playSessionId = null;
		}
	}

	protected override onAfterLoad(): void {
		this.detectPlayMode();
		this.startProgressReporting();
	}

	private detectPlayMode(): void {
		const node = this.getAudioNode();
		if (!node) {
			this.isDirectPlay = false;
			return;
		}
		this.isDirectPlay = isFinite(node.duration) && node.duration > 0;
	}

	protected override onDestroy(): void {
		this.seekLoadGeneration++;
		if (this.seekDebounceTimer) {
			clearTimeout(this.seekDebounceTimer);
			this.seekDebounceTimer = null;
		}
		this.stopProgressReporting();
		if (this.itemId && this.playSessionId) {
			const position = this.getCurrentTime();
			void jellyfinApi.reportStop(this.itemId, this.playSessionId, position);
		}
		this.playSessionId = null;
		this.itemId = null;
	}

	override play(): void {
		this.isPaused = false;
		super.play();
	}

	override pause(): void {
		this.isPaused = true;
		super.pause();
		this.reportProgressNow(true);
	}

	private startProgressReporting(): void {
		this.stopProgressReporting();
		this.reportInterval = setInterval(() => {
			this.reportProgressNow(this.isPaused);
		}, PROGRESS_REPORT_INTERVAL_MS);
	}

	private stopProgressReporting(): void {
		if (this.reportInterval) {
			clearInterval(this.reportInterval);
			this.reportInterval = null;
		}
	}

	private reportProgressNow(isPaused: boolean): void {
		if (!this.itemId || !this.playSessionId || !this.sessionHealthy) return;
		const position = this.getCurrentTime();
		void (async () => {
			try {
				await jellyfinApi.reportProgress(this.itemId!, this.playSessionId!, position, isPaused);
				this.consecutiveReportFailures = 0;
			} catch {
				this.consecutiveReportFailures++;
				if (this.consecutiveReportFailures >= MAX_REPORT_FAILURES) {
					console.warn(
						`[Jellyfin] ${MAX_REPORT_FAILURES} consecutive report failures, disabling session reporting`,
					);
					this.sessionHealthy = false;
					this.stopProgressReporting();
				}
			}
		})();
	}

	private extractItemId(url: string | undefined): string | null {
		if (!url) return null;
		const match = url.match(/\/api\/stream\/jellyfin\/([^/?]+)/);
		return match?.[1] ?? null;
	}

	private async reloadFromSeekOffset(seconds: number, generation: number): Promise<void> {
		if (generation !== this.seekLoadGeneration) return;
		if (!this.primaryLoadInfo?.url) return;

		const wasPlaying = this.howl?.playing() ?? false;
		this.stopProgressReporting();
		this.skipSessionStartOnNextLoad = true;
		const baseUrl = this.primaryLoadInfo.url.replace(/&start_seconds=[^&]*/g, '');
		const seekedUrl = seconds > 0 ? `${baseUrl}&start_seconds=${seconds}` : baseUrl;

		try {
			await super.load({ ...this.primaryLoadInfo, url: seekedUrl });
			if (generation !== this.seekLoadGeneration) return;
			if (wasPlaying) this.play();
		} catch (error) {
			if (generation !== this.seekLoadGeneration) return;
			console.warn('[Jellyfin] seek reload failed:', error);
			this.emitError({ code: 'SEEK_LOAD_ERROR', message: 'Failed to seek Jellyfin stream' });
		}
	}
}
