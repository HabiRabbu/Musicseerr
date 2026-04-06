import { describe, it, expect, vi } from 'vitest';

import { createPlaybackSource } from './createSource';
import { YouTubePlaybackSource } from './YouTubePlaybackSource';
import { NativeAudioSource } from './NativeAudioSource';

vi.mock('./audioElement', () => ({
	getAudioElement: vi.fn(() => ({
		src: '',
		volume: 1,
		currentTime: 0,
		duration: 0,
		ended: false,
		play: vi.fn(() => Promise.resolve()),
		pause: vi.fn(),
		load: vi.fn(),
		addEventListener: vi.fn(),
		removeEventListener: vi.fn(),
		error: null
	}))
}));

describe('createPlaybackSource', () => {
	it('returns a YouTubePlaybackSource for "youtube"', () => {
		const source = createPlaybackSource('youtube');
		expect(source).toBeInstanceOf(YouTubePlaybackSource);
	});

	it('returns a NativeAudioSource for "jellyfin"', () => {
		const source = createPlaybackSource('jellyfin', {
			url: 'https://example.test/audio',
			seekable: true
		});
		expect(source).toBeInstanceOf(NativeAudioSource);
		expect(source.type).toBe('jellyfin');
	});

	it('returns a NativeAudioSource for "local"', () => {
		const source = createPlaybackSource('local', { url: '/api/v1/stream/local/1', seekable: true });
		expect(source).toBeInstanceOf(NativeAudioSource);
		expect(source.type).toBe('local');
	});

	it('throws if jellyfin source options are missing', () => {
		expect(() => createPlaybackSource('jellyfin')).toThrow('requires url and seekable options');
	});

	it('throws if local source options are missing', () => {
		expect(() => createPlaybackSource('local')).toThrow('requires url and seekable options');
	});

	it('throws for unknown source type at runtime', () => {
		expect(() => createPlaybackSource('unknown' as never)).toThrow('Unknown source type');
	});
});
