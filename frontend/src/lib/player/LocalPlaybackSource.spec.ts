import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const mockHowlInstance = {
	on: vi.fn().mockReturnThis(),
	play: vi.fn(),
	pause: vi.fn(),
	seek: vi.fn().mockReturnValue(0),
	volume: vi.fn(),
	duration: vi.fn().mockReturnValue(0),
	unload: vi.fn()
};

vi.mock('howler', () => ({
	Howl: vi.fn().mockImplementation(() => mockHowlInstance)
}));

import { LocalPlaybackSource } from './LocalPlaybackSource';

describe('LocalPlaybackSource', () => {
	let source: LocalPlaybackSource;

	beforeEach(() => {
		vi.clearAllMocks();
		mockHowlInstance.on.mockReturnThis();
		source = new LocalPlaybackSource();
	});

	afterEach(() => {
		source.destroy();
	});

	it('has type "howler"', () => {
		expect(source.type).toBe('howler');
	});

	it('loads audio with html5 mode and explicit format', async () => {
		const { Howl } = await import('howler');

		mockHowlInstance.on.mockImplementation((event: string, cb: () => void) => {
			if (event === 'load') setTimeout(cb, 0);
			return mockHowlInstance;
		});

		await source.load({ url: '/api/stream/local/42', format: 'flac' });

		expect(Howl).toHaveBeenCalledWith(
			expect.objectContaining({
				src: ['/api/stream/local/42'],
				html5: true,
				format: ['flac']
			})
		);
	});

	it('implements PlaybackSource interface methods', () => {
		expect(typeof source.load).toBe('function');
		expect(typeof source.play).toBe('function');
		expect(typeof source.pause).toBe('function');
		expect(typeof source.seekTo).toBe('function');
		expect(typeof source.setVolume).toBe('function');
		expect(typeof source.getCurrentTime).toBe('function');
		expect(typeof source.getDuration).toBe('function');
		expect(typeof source.destroy).toBe('function');
		expect(typeof source.onStateChange).toBe('function');
		expect(typeof source.onReady).toBe('function');
		expect(typeof source.onError).toBe('function');
		expect(typeof source.onProgress).toBe('function');
	});
});
