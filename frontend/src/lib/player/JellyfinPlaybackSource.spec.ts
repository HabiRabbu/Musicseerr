import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest';

const mockHowlInstance = {
	on: vi.fn().mockReturnThis(),
	play: vi.fn(),
	pause: vi.fn(),
	seek: vi.fn().mockReturnValue(25.0),
	volume: vi.fn(),
	duration: vi.fn().mockReturnValue(200),
	unload: vi.fn(),
	_sounds: [{ _node: null as HTMLAudioElement | null }],
};

vi.mock('howler', () => ({
	Howl: vi.fn().mockImplementation(() => mockHowlInstance)
}));

const mockStartSession = vi.fn().mockResolvedValue('session-abc-123');
const mockReportProgress = vi.fn().mockResolvedValue(undefined);
const mockReportStop = vi.fn().mockResolvedValue(undefined);

vi.mock('./jellyfinPlaybackApi', () => ({
	startSession: (...args: unknown[]) => mockStartSession(...args),
	reportProgress: (...args: unknown[]) => mockReportProgress(...args),
	reportStop: (...args: unknown[]) => mockReportStop(...args)
}));

import { JellyfinPlaybackSource } from './JellyfinPlaybackSource';

describe('JellyfinPlaybackSource', () => {
	let source: JellyfinPlaybackSource;

	beforeAll(async () => {
		await import('howler');
	});

	beforeEach(() => {
		vi.clearAllMocks();
		vi.useFakeTimers();
		mockHowlInstance.on.mockReturnThis();
		mockStartSession.mockResolvedValue('session-abc-123');
		source = new JellyfinPlaybackSource();
	});

	afterEach(() => {
		source.destroy();
		vi.useRealTimers();
	});

	it('has type "jellyfin"', () => {
		expect(source.type).toBe('jellyfin');
	});

	it('starts a playback session before loading audio', async () => {
		vi.useRealTimers();

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42?format=aac&bitrate=128000',
			format: 'aac'
		});

		expect(mockStartSession).toHaveBeenCalledWith('jf-item-42');

		vi.useFakeTimers();
	});

	it('continues loading even if session start fails', async () => {
		const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
		mockStartSession.mockRejectedValueOnce(new Error('Jellyfin unavailable'));

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		expect(mockStartSession).toHaveBeenCalled();
		expect(warnSpy).toHaveBeenCalledWith(
			expect.stringContaining('session start failed'),
			expect.any(Error)
		);
		warnSpy.mockRestore();
	});

	it('reports progress at 10-second intervals', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		mockReportProgress.mockClear();

		await vi.advanceTimersByTimeAsync(10_000);

		expect(mockReportProgress).toHaveBeenCalledWith('jf-item-42', 'session-abc-123', 25.0, false);
	});

	it('reports paused state on pause', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		mockReportProgress.mockClear();
		source.pause();

		expect(mockHowlInstance.pause).toHaveBeenCalled();
		expect(mockReportProgress).toHaveBeenCalledWith(
			'jf-item-42',
			'session-abc-123',
			25.0,
			true
		);
	});

	it('reports stop on destroy', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		source.destroy();

		expect(mockReportStop).toHaveBeenCalledWith('jf-item-42', 'session-abc-123', 25.0);
		expect(mockHowlInstance.unload).toHaveBeenCalled();
	});

	it('does not report stop if no session was established', async () => {
		mockStartSession.mockRejectedValueOnce(new Error('Failed'));

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		source.destroy();

		expect(mockReportStop).not.toHaveBeenCalled();
	});

	it('extracts item ID from URL when videoId is not provided', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			url: '/api/stream/jellyfin/some-item-id?format=aac&bitrate=128000',
			format: 'aac'
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		expect(mockStartSession).toHaveBeenCalledWith('some-item-id');
	});

	it('disables progress reporting after 3 consecutive failures', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		const loadPromise = source.load({
			videoId: 'jf-item-42',
			url: '/api/stream/jellyfin/jf-item-42',
			format: 'aac',
		});
		await vi.advanceTimersByTimeAsync(10);
		await loadPromise;

		const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
		mockReportProgress.mockRejectedValue(new Error('Server error'));

		await vi.advanceTimersByTimeAsync(10_000);
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(10_000);
		await vi.advanceTimersByTimeAsync(0);
		await vi.advanceTimersByTimeAsync(10_000);
		await vi.advanceTimersByTimeAsync(0);

		expect(warnSpy).toHaveBeenCalledWith(
			expect.stringContaining('disabling session reporting'),
		);

		mockReportProgress.mockClear();
		await vi.advanceTimersByTimeAsync(10_000);
		await vi.advanceTimersByTimeAsync(0);

		expect(mockReportProgress).not.toHaveBeenCalled();

		warnSpy.mockRestore();
	});
});
