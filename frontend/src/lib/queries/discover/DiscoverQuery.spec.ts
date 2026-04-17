import { describe, expect, it, vi, beforeEach } from 'vitest';
import { DiscoverQueryKeyFactory } from './DiscoverQueryKeyFactory';

vi.mock('@tanstack/svelte-query', () => ({
	createQuery: vi.fn((factory: () => Record<string, unknown>) => {
		const opts = factory();
		return opts;
	}),
	queryOptions: vi.fn((opts: Record<string, unknown>) => opts)
}));

vi.mock('$lib/api/client', async () => {
	class ApiErrorMock extends Error {
		readonly status: number;
		readonly code: string;
		readonly details: unknown;
		constructor(status: number, message: string, code = '', details: unknown = null) {
			super(message);
			this.name = 'ApiError';
			this.status = status;
			this.code = code;
			this.details = details;
		}
	}
	return {
		ApiError: ApiErrorMock,
		api: {
			global: {
				get: vi.fn(),
				post: vi.fn()
			}
		}
	};
});

import { api } from '$lib/api/client';
import { createQuery } from '@tanstack/svelte-query';

const mockPost = vi.mocked(api.global.post);
const mockCreateQuery = vi.mocked(createQuery);

beforeEach(() => {
	vi.clearAllMocks();
});

describe('DiscoverQueryKeyFactory', () => {
	describe('prefix', () => {
		it('is [discover]', () => {
			expect(DiscoverQueryKeyFactory.prefix).toEqual(['discover']);
		});
	});

	describe('discover', () => {
		it('returns expected key shape', () => {
			const key = DiscoverQueryKeyFactory.discover('listenbrainz');
			expect(key).toEqual(['discover', 'listenbrainz']);
		});

		it('produces different keys for different sources', () => {
			const lbKey = DiscoverQueryKeyFactory.discover('listenbrainz');
			const lfmKey = DiscoverQueryKeyFactory.discover('lastfm');
			expect(lbKey).not.toEqual(lfmKey);
		});

		it('starts with the discover prefix', () => {
			const key = DiscoverQueryKeyFactory.discover('listenbrainz');
			expect(key[0]).toBe('discover');
		});
	});

	describe('playlistSuggestions', () => {
		it('returns expected key shape with no source', () => {
			const key = DiscoverQueryKeyFactory.playlistSuggestions('pl-1');
			expect(key).toEqual(['discover', 'playlist-suggestions', 'pl-1', null]);
		});

		it('returns expected key shape with source', () => {
			const key = DiscoverQueryKeyFactory.playlistSuggestions('pl-1', 'listenbrainz');
			expect(key).toEqual(['discover', 'playlist-suggestions', 'pl-1', 'listenbrainz']);
		});

		it('produces different keys for different playlist IDs', () => {
			const key1 = DiscoverQueryKeyFactory.playlistSuggestions('pl-1');
			const key2 = DiscoverQueryKeyFactory.playlistSuggestions('pl-2');
			expect(key1).not.toEqual(key2);
		});

		it('produces different keys for different sources', () => {
			const lbKey = DiscoverQueryKeyFactory.playlistSuggestions('pl-1', 'listenbrainz');
			const lfmKey = DiscoverQueryKeyFactory.playlistSuggestions('pl-1', 'lastfm');
			expect(lbKey).not.toEqual(lfmKey);
		});

		it('null source matches omitted source', () => {
			const noSource = DiscoverQueryKeyFactory.playlistSuggestions('pl-1');
			const nullSource = DiscoverQueryKeyFactory.playlistSuggestions('pl-1', null);
			expect(noSource).toEqual(nullSource);
		});

		it('starts with the discover prefix', () => {
			const key = DiscoverQueryKeyFactory.playlistSuggestions('pl-1');
			expect(key[0]).toBe('discover');
		});
	});

	describe('cross-key isolation', () => {
		it('discover and playlistSuggestions keys differ for same string input', () => {
			const discoverKey = DiscoverQueryKeyFactory.discover('listenbrainz');
			const playlistKey = DiscoverQueryKeyFactory.playlistSuggestions('listenbrainz');
			expect(discoverKey).not.toEqual(playlistKey);
		});
	});
});

describe('getPlaylistSuggestionsQuery source propagation', () => {
	it('passes listenbrainz source in request body', async () => {
		mockPost.mockResolvedValue({ playlist_id: 'pl-1', suggestions: { items: [] } });

		const { getPlaylistSuggestionsQuery } = await import('./DiscoverQuery.svelte');

		const getter = () => ({
			playlistId: 'pl-1',
			count: 10,
			source: 'listenbrainz' as const,
			enabled: true
		});

		getPlaylistSuggestionsQuery(getter);

		expect(mockCreateQuery).toHaveBeenCalled();
		const factory = mockCreateQuery.mock.calls[
			mockCreateQuery.mock.calls.length - 1
		][0] as unknown as () => Record<string, unknown>;
		const opts = factory();
		const queryFn = opts.queryFn as (ctx: { signal: AbortSignal }) => Promise<unknown>;
		await queryFn({ signal: new AbortController().signal });

		expect(mockPost).toHaveBeenCalledTimes(1);
		const [, body] = mockPost.mock.calls[0];
		expect((body as Record<string, unknown>).source).toBe('listenbrainz');
	});

	it('passes lastfm source in request body', async () => {
		mockPost.mockResolvedValue({ playlist_id: 'pl-1', suggestions: { items: [] } });

		const { getPlaylistSuggestionsQuery } = await import('./DiscoverQuery.svelte');

		const getter = () => ({
			playlistId: 'pl-1',
			count: 10,
			source: 'lastfm' as const,
			enabled: true
		});

		getPlaylistSuggestionsQuery(getter);

		const factory = mockCreateQuery.mock.calls[
			mockCreateQuery.mock.calls.length - 1
		][0] as unknown as () => Record<string, unknown>;
		const opts = factory();
		const queryFn = opts.queryFn as (ctx: { signal: AbortSignal }) => Promise<unknown>;
		await queryFn({ signal: new AbortController().signal });

		expect(mockPost).toHaveBeenCalledTimes(1);
		const [, body] = mockPost.mock.calls[0];
		expect((body as Record<string, unknown>).source).toBe('lastfm');
	});
});

describe('getRadioQuery source propagation', () => {
	it('passes source in request body', async () => {
		mockPost.mockResolvedValue({ items: [] });

		const { getRadioQuery } = await import('./DiscoverQuery.svelte');

		const getter = () => ({
			seedType: 'artist',
			seedId: 'mbid-123',
			source: 'listenbrainz' as const
		});

		getRadioQuery(getter);

		const factory = mockCreateQuery.mock.calls[
			mockCreateQuery.mock.calls.length - 1
		][0] as unknown as () => Record<string, unknown>;
		const opts = factory();
		const queryFn = opts.queryFn as (ctx: { signal: AbortSignal }) => Promise<unknown>;
		await queryFn({ signal: new AbortController().signal });

		expect(mockPost).toHaveBeenCalledTimes(1);
		const [, body] = mockPost.mock.calls[0];
		expect((body as Record<string, unknown>).source).toBe('listenbrainz');
	});

	it('passes lastfm source in request body', async () => {
		mockPost.mockResolvedValue({ items: [] });

		const { getRadioQuery } = await import('./DiscoverQuery.svelte');

		const getter = () => ({
			seedType: 'artist',
			seedId: 'mbid-456',
			source: 'lastfm' as const
		});

		getRadioQuery(getter);

		const factory = mockCreateQuery.mock.calls[
			mockCreateQuery.mock.calls.length - 1
		][0] as unknown as () => Record<string, unknown>;
		const opts = factory();
		const queryFn = opts.queryFn as (ctx: { signal: AbortSignal }) => Promise<unknown>;
		await queryFn({ signal: new AbortController().signal });

		expect(mockPost).toHaveBeenCalledTimes(1);
		const [, body] = mockPost.mock.calls[0];
		expect((body as Record<string, unknown>).source).toBe('lastfm');
	});
});
