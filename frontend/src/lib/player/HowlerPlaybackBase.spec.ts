import { describe, it, expect, vi, beforeAll, beforeEach, afterEach } from 'vitest';

const mockHowlInstance = {
	on: vi.fn().mockReturnThis(),
	play: vi.fn(),
	pause: vi.fn(),
	seek: vi.fn().mockReturnValue(0),
	volume: vi.fn(),
	duration: vi.fn().mockReturnValue(0),
	unload: vi.fn(),
	_sounds: [{ _node: null as HTMLAudioElement | null }],
};

vi.mock('howler', () => ({
	Howl: vi.fn().mockImplementation(() => mockHowlInstance)
}));

import { LocalPlaybackSource } from './LocalPlaybackSource';

describe('HowlerPlaybackBase', () => {
	let source: LocalPlaybackSource;

	beforeAll(async () => {
		await import('howler');
	});

	beforeEach(() => {
		vi.clearAllMocks();
		mockHowlInstance.on.mockReturnThis();
		mockHowlInstance.seek.mockReturnValue(42.5);
		mockHowlInstance.duration.mockReturnValue(180);
		source = new LocalPlaybackSource();
	});

	afterEach(() => {
		source.destroy();
	});

	it('throws if url is not provided', async () => {
		await expect(source.load({})).rejects.toThrow('url is required');
	});

	it('creates Howl with html5: true and explicit format', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/123', format: 'flac' });

		const { Howl } = await import('howler');
		expect(Howl).toHaveBeenCalledWith({
			src: ['/api/stream/local/123'],
			html5: true,
			format: ['flac'],
			volume: 0.75
		});
	});

	it('defaults format to aac when not provided', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/123' });

		const { Howl } = await import('howler');
		expect(Howl).toHaveBeenCalledWith(
			expect.objectContaining({
				format: ['aac']
			})
		);
	});

	it('delegates play/pause/seekTo to Howl instance', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		source.play();
		expect(mockHowlInstance.play).toHaveBeenCalled();

		source.pause();
		expect(mockHowlInstance.pause).toHaveBeenCalled();

		source.seekTo(30);
		expect(mockHowlInstance.seek).toHaveBeenCalledWith(30);
	});

	it('converts volume from 0-100 to 0-1 range', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		source.setVolume(50);
		expect(mockHowlInstance.volume).toHaveBeenCalledWith(0.5);

		source.setVolume(0);
		expect(mockHowlInstance.volume).toHaveBeenCalledWith(0);

		source.setVolume(100);
		expect(mockHowlInstance.volume).toHaveBeenCalledWith(1);
	});

	it('clamps volume to 0-100 range', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		source.setVolume(150);
		expect(mockHowlInstance.volume).toHaveBeenCalledWith(1);

		source.setVolume(-10);
		expect(mockHowlInstance.volume).toHaveBeenCalledWith(0);
	});

	it('returns current time and duration from Howl', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		expect(source.getCurrentTime()).toBe(42.5);
		expect(source.getDuration()).toBe(180);
	});

	it('returns 0 for time/duration when no Howl exists', () => {
		expect(source.getCurrentTime()).toBe(0);
		expect(source.getDuration()).toBe(0);
	});

	it('unloads Howl on destroy', async () => {
		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });
		source.destroy();

		expect(mockHowlInstance.unload).toHaveBeenCalled();
	});

	it('fires ready callbacks on Howl load event', async () => {
		const readyCb = vi.fn();
		source.onReady(readyCb);

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		expect(readyCb).toHaveBeenCalledOnce();
	});

	it('fires error callbacks on Howl loaderror event', async () => {
		const errorCb = vi.fn();
		source.onError(errorCb);

		mockHowlInstance.on.mockImplementation((event: string, cb: (...args: unknown[]) => void) => {
			if (event === 'loaderror') setTimeout(() => cb(0, 'Network error'), 0);
			return mockHowlInstance;
		});

		await expect(source.load({ url: '/api/stream/local/1' })).rejects.toEqual(
			expect.objectContaining({ code: 'LOAD_ERROR' })
		);

		expect(errorCb).toHaveBeenCalledWith(
			expect.objectContaining({ code: 'LOAD_ERROR', message: 'Network error' })
		);
	});

	it('fires state callbacks on Howl play/pause/end events', async () => {
		const stateHistory: string[] = [];
		source.onStateChange((state) => stateHistory.push(state));

		const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
		mockHowlInstance.on.mockImplementation(
			(event: string, cb: (...args: unknown[]) => void) => {
				if (!eventHandlers[event]) eventHandlers[event] = [];
				eventHandlers[event].push(cb);
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			}
		);

		await source.load({ url: '/api/stream/local/1' });

		eventHandlers['play']?.forEach((cb) => cb());
		eventHandlers['pause']?.forEach((cb) => cb());
		eventHandlers['end']?.forEach((cb) => cb());

		expect(stateHistory).toContain('playing');
		expect(stateHistory).toContain('paused');
		expect(stateHistory).toContain('ended');
	});

	it('rejects with LOAD_TIMEOUT if Howl does not load in time', async () => {
		vi.useFakeTimers();

		mockHowlInstance.on.mockReturnThis();

		const errorCb = vi.fn();
		source.onError(errorCb);

		const loadPromise = source.load({ url: '/api/stream/local/1' });
		const assertion = expect(loadPromise).rejects.toEqual(
			expect.objectContaining({ code: 'LOAD_TIMEOUT' })
		);

		await vi.advanceTimersByTimeAsync(15_000);
		await assertion;

		expect(errorCb).toHaveBeenCalledWith(expect.objectContaining({ code: 'LOAD_TIMEOUT' }));

		vi.useRealTimers();
	});

	it('emits paused (not playing) when seeking while paused', async () => {
		const stateHistory: string[] = [];
		source.onStateChange((state) => stateHistory.push(state));

		const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
		mockHowlInstance.on.mockImplementation(
			(event: string, cb: (...args: unknown[]) => void) => {
				if (!eventHandlers[event]) eventHandlers[event] = [];
				eventHandlers[event].push(cb);
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			}
		);

		await source.load({ url: '/api/stream/local/1' });

		stateHistory.length = 0;

		eventHandlers['seek']?.forEach((cb) => cb());

		expect(stateHistory).toEqual(['paused']);
	});

	it('emits playing when seeking while playing', async () => {
		const stateHistory: string[] = [];
		source.onStateChange((state) => stateHistory.push(state));

		const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
		mockHowlInstance.on.mockImplementation(
			(event: string, cb: (...args: unknown[]) => void) => {
				if (!eventHandlers[event]) eventHandlers[event] = [];
				eventHandlers[event].push(cb);
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			}
		);

		await source.load({ url: '/api/stream/local/1' });

		eventHandlers['play']?.forEach((cb) => cb());
		stateHistory.length = 0;

		eventHandlers['seek']?.forEach((cb) => cb());

		expect(stateHistory).toEqual(['playing']);
	});

	it('fires error callbacks on Howl playerror event', async () => {
		const errorCb = vi.fn();
		source.onError(errorCb);

		const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
		mockHowlInstance.on.mockImplementation(
			(event: string, cb: (...args: unknown[]) => void) => {
				if (!eventHandlers[event]) eventHandlers[event] = [];
				eventHandlers[event].push(cb);
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			}
		);

		await source.load({ url: '/api/stream/local/1' });

		eventHandlers['playerror']?.forEach((cb) => cb(0, 'Media decode error'));

		expect(errorCb).toHaveBeenCalledWith(
			expect.objectContaining({ code: 'PLAY_ERROR', message: 'Media decode error' })
		);
	});

	it('emits loading state at the start of load()', async () => {
		const stateHistory: string[] = [];
		source.onStateChange((state) => stateHistory.push(state));

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/1' });

		expect(stateHistory[0]).toBe('loading');
	});

	describe('network stall detection', () => {
		let mockAudioNode: Record<string, unknown>;
		let nativeListeners: Record<string, EventListener>;

		beforeEach(() => {
			nativeListeners = {};
			mockAudioNode = {
				addEventListener: vi.fn((event: string, handler: EventListener) => {
					nativeListeners[event] = handler;
				}),
				removeEventListener: vi.fn(),
				error: null,
			};
			mockHowlInstance._sounds = [{ _node: mockAudioNode as unknown as HTMLAudioElement }];
		});

		it('fires NETWORK_STALL error after 15s stall timeout', async () => {
			vi.useFakeTimers();
			const errorCb = vi.fn();
			source.onError(errorCb);

			const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
			mockHowlInstance.on.mockImplementation(
				(event: string, cb: (...args: unknown[]) => void) => {
					if (!eventHandlers[event]) eventHandlers[event] = [];
					eventHandlers[event].push(cb);
					if (event === 'load') setTimeout(cb, 0);
					return mockHowlInstance;
				},
			);

			const loadPromise = source.load({ url: '/api/stream/local/1' });
			await vi.advanceTimersByTimeAsync(10);
			await loadPromise;

			eventHandlers['play']?.forEach((cb) => cb());
			nativeListeners['waiting']?.(new Event('waiting'));

			await vi.advanceTimersByTimeAsync(15_000);

			expect(errorCb).toHaveBeenCalledWith(
				expect.objectContaining({ code: 'NETWORK_STALL' }),
			);

			vi.useRealTimers();
		});

		it('cancels stall timeout when playback resumes', async () => {
			vi.useFakeTimers();
			const errorCb = vi.fn();
			source.onError(errorCb);

			const eventHandlers: Record<string, ((...args: unknown[]) => void)[]> = {};
			mockHowlInstance.on.mockImplementation(
				(event: string, cb: (...args: unknown[]) => void) => {
					if (!eventHandlers[event]) eventHandlers[event] = [];
					eventHandlers[event].push(cb);
					if (event === 'load') setTimeout(cb, 0);
					return mockHowlInstance;
				},
			);

			const loadPromise = source.load({ url: '/api/stream/local/1' });
			await vi.advanceTimersByTimeAsync(10);
			await loadPromise;

			eventHandlers['play']?.forEach((cb) => cb());
			nativeListeners['waiting']?.(new Event('waiting'));
			await vi.advanceTimersByTimeAsync(5_000);

			nativeListeners['playing']?.(new Event('playing'));
			await vi.advanceTimersByTimeAsync(15_000);

			expect(errorCb).not.toHaveBeenCalled();

			vi.useRealTimers();
		});

		it('fires MEDIA_ERROR on native audio error', async () => {
			const errorCb = vi.fn();
			source.onError(errorCb);

			mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			});

			await source.load({ url: '/api/stream/local/1' });

			mockAudioNode.error = { code: 2 };
			nativeListeners['error']?.(new Event('error'));

			expect(errorCb).toHaveBeenCalledWith(
				expect.objectContaining({
					code: 'MEDIA_ERROR_2',
					message: expect.stringContaining('Network error'),
				}),
			);
		});

		it('removes native listeners on destroy', async () => {
			mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
				if (event === 'load') setTimeout(cb, 0);
				return mockHowlInstance;
			});

			await source.load({ url: '/api/stream/local/1' });
			source.destroy();

			expect(mockAudioNode.removeEventListener).toHaveBeenCalledWith(
				'waiting',
				expect.any(Function),
			);
			expect(mockAudioNode.removeEventListener).toHaveBeenCalledWith(
				'stalled',
				expect.any(Function),
			);
			expect(mockAudioNode.removeEventListener).toHaveBeenCalledWith(
				'error',
				expect.any(Function),
			);
		});
	});
});
