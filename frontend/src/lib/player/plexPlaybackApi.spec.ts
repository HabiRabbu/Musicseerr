import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockPost = vi.fn();
const mockGet = vi.fn();

vi.mock('$lib/api/client', () => {
	class _ApiError extends Error {
		status: number;
		code: string;
		details: unknown;
		constructor(status: number, code: string, message: string, details?: unknown) {
			super(message);
			this.status = status;
			this.code = code;
			this.details = details;
		}
	}
	return {
		api: {
			global: {
				post: (...args: unknown[]) => mockPost(...args),
				get: (...args: unknown[]) => mockGet(...args)
			}
		},
		ApiError: _ApiError
	};
});

vi.mock('$lib/constants', () => ({
	API: {
		stream: {
			plexScrobble: (key: string) => `/api/v1/stream/plex/${key}/scrobble`,
			plexNowPlaying: (key: string) => `/api/v1/stream/plex/${key}/now-playing`
		},
		settingsPlex: () => '/api/v1/settings/plex'
	}
}));

import {
	reportPlexScrobble,
	reportPlexNowPlaying,
	isPlexScrobbleEnabled,
	resetPlexScrobblePreference
} from './plexPlaybackApi';

describe('plexPlaybackApi', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		resetPlexScrobblePreference();
	});

	describe('reportPlexScrobble', () => {
		it('calls scrobble endpoint when enabled', async () => {
			expect.assertions(2);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockResolvedValueOnce(undefined);

			await reportPlexScrobble('12345');

			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/plex/12345/scrobble');
			expect(mockGet).toHaveBeenCalledWith('/api/v1/settings/plex');
		});

		it('does not call scrobble when disabled', async () => {
			expect.assertions(1);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: false });

			await reportPlexScrobble('12345');

			expect(mockPost).not.toHaveBeenCalled();
		});

		it('warns on error without throwing', async () => {
			expect.assertions(1);
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockRejectedValueOnce(new Error('Network down'));

			await reportPlexScrobble('12345');

			expect(warnSpy).toHaveBeenCalled();
			warnSpy.mockRestore();
		});

		it('defaults to disabled when settings fetch fails', async () => {
			expect.assertions(1);
			mockGet.mockRejectedValueOnce(new Error('fetch failed'));

			await reportPlexScrobble('12345');

			expect(mockPost).not.toHaveBeenCalled();
		});
	});

	describe('reportPlexNowPlaying', () => {
		it('calls now-playing endpoint when enabled', async () => {
			expect.assertions(1);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockResolvedValueOnce(undefined);

			await reportPlexNowPlaying('67890');

			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/plex/67890/now-playing');
		});

		it('does not call now-playing when disabled', async () => {
			expect.assertions(1);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: false });

			await reportPlexNowPlaying('67890');

			expect(mockPost).not.toHaveBeenCalled();
		});

		it('warns on error without throwing', async () => {
			expect.assertions(1);
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockRejectedValueOnce(new Error('timeout'));

			await reportPlexNowPlaying('67890');

			expect(warnSpy).toHaveBeenCalled();
			warnSpy.mockRestore();
		});
	});

	describe('isPlexScrobbleEnabled', () => {
		it('defaults to false before any load', () => {
			expect.assertions(1);
			expect(isPlexScrobbleEnabled()).toBe(false);
		});

		it('reflects loaded preference', async () => {
			expect.assertions(1);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: false });
			mockPost.mockResolvedValueOnce(undefined);

			await reportPlexScrobble('test');

			expect(isPlexScrobbleEnabled()).toBe(false);
		});
	});

	describe('resetPlexScrobblePreference', () => {
		it('resets cache so next call re-fetches', async () => {
			expect.assertions(2);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: false });
			await reportPlexScrobble('test');

			resetPlexScrobblePreference();

			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockResolvedValueOnce(undefined);
			await reportPlexScrobble('test2');

			expect(mockGet).toHaveBeenCalledTimes(2);
			expect(mockPost).toHaveBeenCalledTimes(1);
		});
	});

	describe('preference caching', () => {
		it('fetches only once across multiple calls', async () => {
			expect.assertions(1);
			mockGet.mockResolvedValueOnce({ scrobble_to_plex: true });
			mockPost.mockResolvedValue(undefined);

			await reportPlexScrobble('a');
			await reportPlexScrobble('b');
			await reportPlexNowPlaying('c');

			expect(mockGet).toHaveBeenCalledTimes(1);
		});
	});
});
