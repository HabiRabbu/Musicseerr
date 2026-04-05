import { describe, it, expect, vi, beforeEach } from 'vitest';

const mockPost = vi.fn();

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
				post: (...args: unknown[]) => mockPost(...args)
			}
		},
		ApiError: _ApiError
	};
});

import * as api from './jellyfinPlaybackApi';

describe('jellyfinPlaybackApi', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('startSession', () => {
		it('sends POST to start endpoint and returns play_session_id', async () => {
			mockPost.mockResolvedValueOnce({ play_session_id: 'sess-123', item_id: 'item-456' });

			const result = await api.startSession('item-456');

			expect(result).toBe('sess-123');
			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/jellyfin/item-456/start', undefined);
		});

		it('sends existing play_session_id when provided', async () => {
			mockPost.mockResolvedValueOnce({ play_session_id: 'sess-123', item_id: 'item-456' });

			await api.startSession('item-456', 'sess-existing');

			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/jellyfin/item-456/start', {
				play_session_id: 'sess-existing'
			});
		});

		it('throws on non-ok response', async () => {
			const { ApiError } = await import('$lib/api/client');
			mockPost.mockRejectedValueOnce(new ApiError(403, 'forbidden', 'Not allowed'));

			await expect(api.startSession('item-789')).rejects.toThrow(
				'Failed to start Jellyfin playback session'
			);
		});
	});

	describe('reportProgress', () => {
		it('sends POST with correct body and returns true on success', async () => {
			mockPost.mockResolvedValueOnce(undefined);

			const ok = await api.reportProgress('item-1', 'sess-1', 42.5, false);

			expect(ok).toBe(true);
			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/jellyfin/item-1/progress', {
				play_session_id: 'sess-1',
				position_seconds: 42.5,
				is_paused: false
			});
		});

		it('warns on network errors without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockPost.mockRejectedValueOnce(new Error('Network down'));

			await expect(api.reportProgress('item-1', 'sess-1', 10, false)).resolves.toBe(false);
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('network error'));
			warnSpy.mockRestore();
		});

		it('warns on non-ok response without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			const { ApiError } = await import('$lib/api/client');
			mockPost.mockRejectedValueOnce(new ApiError(500, 'server_error', 'Internal error'));

			await expect(api.reportProgress('item-1', 'sess-1', 10, false)).resolves.toBe(false);
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('500'));
			warnSpy.mockRestore();
		});
	});

	describe('reportStop', () => {
		it('sends POST with correct body and returns true on success', async () => {
			mockPost.mockResolvedValueOnce(undefined);

			const ok = await api.reportStop('item-1', 'sess-1', 120.0);

			expect(ok).toBe(true);
			expect(mockPost).toHaveBeenCalledWith('/api/v1/stream/jellyfin/item-1/stop', {
				play_session_id: 'sess-1',
				position_seconds: 120.0
			});
		});

		it('swallows errors silently', async () => {
			mockPost.mockRejectedValueOnce(new Error('Network down'));

			await expect(api.reportStop('item-1', 'sess-1', 60)).resolves.toBe(false);
		});

		it('warns on non-ok response without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			const { ApiError } = await import('$lib/api/client');
			mockPost.mockRejectedValueOnce(new ApiError(502, 'bad_gateway', 'Bad gateway'));

			await expect(api.reportStop('item-1', 'sess-1', 60)).resolves.toBe(false);
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('502'));
			warnSpy.mockRestore();
		});
	});
});
