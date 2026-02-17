import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from './jellyfinPlaybackApi';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

describe('jellyfinPlaybackApi', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	describe('startSession', () => {
		it('sends POST to start endpoint and returns play_session_id', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: true,
				json: () => Promise.resolve({ play_session_id: 'sess-123', item_id: 'item-456' })
			});

			const result = await api.startSession('item-456');

			expect(result).toBe('sess-123');
			expect(mockFetch).toHaveBeenCalledWith('/api/stream/jellyfin/item-456/start', {
				method: 'POST'
			});
		});

		it('throws on non-ok response', async () => {
			mockFetch.mockResolvedValueOnce({
				ok: false,
				status: 403,
				text: () => Promise.resolve('Not allowed')
			});

			await expect(api.startSession('item-789')).rejects.toThrow(
				'Failed to start Jellyfin playback session'
			);
		});
	});

	describe('reportProgress', () => {
		it('sends POST with correct body', async () => {
			mockFetch.mockResolvedValueOnce({ ok: true });

			await api.reportProgress('item-1', 'sess-1', 42.5, false);

			expect(mockFetch).toHaveBeenCalledWith('/api/stream/jellyfin/item-1/progress', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					play_session_id: 'sess-1',
					position_seconds: 42.5,
					is_paused: false
				})
			});
		});

		it('warns on network errors without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockFetch.mockRejectedValueOnce(new Error('Network down'));

			await expect(api.reportProgress('item-1', 'sess-1', 10, false)).resolves.toBeUndefined();
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('network error'));
			warnSpy.mockRestore();
		});

		it('warns on non-ok response without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockFetch.mockResolvedValueOnce({ ok: false, status: 500 });

			await expect(api.reportProgress('item-1', 'sess-1', 10, false)).resolves.toBeUndefined();
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('500'));
			warnSpy.mockRestore();
		});
	});

	describe('reportStop', () => {
		it('sends POST with correct body', async () => {
			mockFetch.mockResolvedValueOnce({ ok: true });

			await api.reportStop('item-1', 'sess-1', 120.0);

			expect(mockFetch).toHaveBeenCalledWith('/api/stream/jellyfin/item-1/stop', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					play_session_id: 'sess-1',
					position_seconds: 120.0
				})
			});
		});

		it('swallows errors silently', async () => {
			mockFetch.mockRejectedValueOnce(new Error('Network down'));

			await expect(api.reportStop('item-1', 'sess-1', 60)).resolves.toBeUndefined();
		});

		it('warns on non-ok response without throwing', async () => {
			const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
			mockFetch.mockResolvedValueOnce({ ok: false, status: 502 });

			await expect(api.reportStop('item-1', 'sess-1', 60)).resolves.toBeUndefined();
			expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('502'));
			warnSpy.mockRestore();
		});
	});
});
