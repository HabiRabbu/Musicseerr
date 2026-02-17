import { describe, it, expect, vi } from 'vitest';

vi.mock('howler', () => ({
	Howl: vi.fn()
}));

import { createPlaybackSource } from './createSource';
import { YouTubePlaybackSource } from './YouTubePlaybackSource';
import { JellyfinPlaybackSource } from './JellyfinPlaybackSource';
import { LocalPlaybackSource } from './LocalPlaybackSource';

describe('createPlaybackSource', () => {
	it('returns a YouTubePlaybackSource for "youtube"', () => {
		const source = createPlaybackSource('youtube');
		expect(source).toBeInstanceOf(YouTubePlaybackSource);
	});

	it('returns a JellyfinPlaybackSource for "jellyfin"', () => {
		const source = createPlaybackSource('jellyfin');
		expect(source).toBeInstanceOf(JellyfinPlaybackSource);
		expect(source.type).toBe('jellyfin');
	});

	it('returns a LocalPlaybackSource for "howler"', () => {
		const source = createPlaybackSource('howler');
		expect(source).toBeInstanceOf(LocalPlaybackSource);
		expect(source.type).toBe('howler');
	});

	it('throws for unknown source type at runtime', () => {
		expect(() => createPlaybackSource('unknown' as never)).toThrow('Unknown source type');
	});
});
