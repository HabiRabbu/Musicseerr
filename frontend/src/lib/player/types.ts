export type PlaybackState = 'idle' | 'loading' | 'playing' | 'paused' | 'ended' | 'buffering' | 'error';

export type SourceType = 'youtube' | 'howler' | 'jellyfin';

export interface PlaybackSource {
	readonly type: SourceType;

	load(info: { videoId?: string; url?: string; token?: string; format?: string }): Promise<void>;
	play(): void;
	pause(): void;
	seekTo(seconds: number): void;
	setVolume(level: number): void;
	getCurrentTime(): number;
	getDuration(): number;
	destroy(): void;

	onStateChange(callback: (state: PlaybackState) => void): void;
	onReady(callback: () => void): void;
	onError(callback: (error: { code: string; message: string }) => void): void;
	onProgress(callback: (currentTime: number, duration: number) => void): void;
}

export interface NowPlaying {
	albumId: string;
	albumName: string;
	artistName: string;
	coverUrl: string | null;
	sourceType: SourceType;
	videoId?: string;
	embedUrl?: string;
	trackName?: string;
	artistId?: string;
	streamUrl?: string;
	format?: string;
}

export type PlaybackMeta = {
	albumId: string;
	albumName: string;
	artistName: string;
	coverUrl: string | null;
	artistId?: string;
};

export interface QueueItem {
	/** Source-specific item identifier (YouTube video ID / Jellyfin item ID / Lidarr track file ID) */
	videoId: string;
	trackName: string;
	artistName: string;
	trackNumber: number;
	albumId: string;
	albumName: string;
	coverUrl: string | null;
	sourceType: SourceType;
	artistId?: string;
	streamUrl?: string;
	format?: string;
}
