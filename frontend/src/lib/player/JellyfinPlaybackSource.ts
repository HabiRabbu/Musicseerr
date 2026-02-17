import type { SourceType } from './types';
import { HowlerPlaybackBase } from './HowlerPlaybackBase';
import * as jellyfinApi from './jellyfinPlaybackApi';

const PROGRESS_REPORT_INTERVAL_MS = 10_000;
const MAX_REPORT_FAILURES = 3;

export class JellyfinPlaybackSource extends HowlerPlaybackBase {
	readonly type: SourceType = 'jellyfin';

	private playSessionId: string | null = null;
	private itemId: string | null = null;
	private reportInterval: ReturnType<typeof setInterval> | null = null;
	private isPaused = false;
	private consecutiveReportFailures = 0;
	private sessionHealthy = true;

	protected override async onBeforeLoad(info: {
		videoId?: string;
		url?: string;
		token?: string;
		format?: string;
	}): Promise<void> {
		this.itemId = info.videoId ?? this.extractItemId(info.url);
		if (!this.itemId) return;

		try {
			this.playSessionId = await jellyfinApi.startSession(this.itemId);
		} catch (err) {
			console.warn('[Jellyfin] session start failed, playback reporting disabled:', err);
			this.playSessionId = null;
		}
	}

	protected override onAfterLoad(): void {
		this.startProgressReporting();
	}

	protected override onDestroy(): void {
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
}
