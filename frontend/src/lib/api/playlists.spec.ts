import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('$lib/constants', () => ({
	API: {
		playlists: {
			list: () => '/api/v1/playlists',
			create: () => '/api/v1/playlists',
			detail: (id: string) => `/api/v1/playlists/${id}`,
			update: (id: string) => `/api/v1/playlists/${id}`,
			delete: (id: string) => `/api/v1/playlists/${id}`,
			addTracks: (id: string) => `/api/v1/playlists/${id}/tracks`,
			removeTrack: (id: string, trackId: string) =>
				`/api/v1/playlists/${id}/tracks/${trackId}`,
			updateTrack: (id: string, trackId: string) =>
				`/api/v1/playlists/${id}/tracks/${trackId}`,
			reorderTrack: (id: string) => `/api/v1/playlists/${id}/tracks/reorder`,
			uploadCover: (id: string) => `/api/v1/playlists/${id}/cover`,
			deleteCover: (id: string) => `/api/v1/playlists/${id}/cover`
		}
	}
}));

import {
	fetchPlaylists,
	fetchPlaylist,
	createPlaylist,
	updatePlaylist,
	deletePlaylist,
	addTracksToPlaylist,
	removeTrackFromPlaylist,
	updatePlaylistTrack,
	reorderPlaylistTrack,
	uploadPlaylistCover,
	deletePlaylistCover,
	queueItemToTrackData
} from './playlists';
import type { QueueItem } from '$lib/player/types';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function jsonResponse(data: unknown, status = 200) {
	return {
		ok: status >= 200 && status < 300,
		status,
		headers: { get: () => null },
		json: () => Promise.resolve(data),
		text: () => Promise.resolve(JSON.stringify(data))
	} as unknown as Response;
}

function errorResponse(status: number, body = '') {
	return {
		ok: false,
		status,
		headers: { get: () => null },
		json: () => Promise.reject(new Error('not json')),
		text: () => Promise.resolve(body)
	} as unknown as Response;
}

beforeEach(() => {
	mockFetch.mockReset();
});

describe('playlists API client', () => {
	describe('fetchPlaylists', () => {
		it('calls GET on list URL and unwraps .playlists', async () => {
			const playlists = [{ id: 'p1', name: 'My Playlist' }];
			mockFetch.mockResolvedValue(jsonResponse({ playlists }));

			const result = await fetchPlaylists();

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists');
			expect(result).toEqual(playlists);
		});

		it('throws on non-ok response', async () => {
			mockFetch.mockResolvedValue(errorResponse(500, 'Server error'));
			await expect(fetchPlaylists()).rejects.toThrow('Server error');
		});
	});

	describe('fetchPlaylist', () => {
		it('calls GET with correct ID', async () => {
			const detail = { id: 'p1', name: 'Test', tracks: [] };
			mockFetch.mockResolvedValue(jsonResponse(detail));

			const result = await fetchPlaylist('p1');

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1');
			expect(result).toEqual(detail);
		});

		it('forwards AbortSignal when provided', async () => {
			const detail = { id: 'p1', name: 'Test', tracks: [] };
			const controller = new AbortController();
			mockFetch.mockResolvedValue(jsonResponse(detail));

			await fetchPlaylist('p1', { signal: controller.signal });

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1', {
				signal: controller.signal
			});
		});

		it('throws when response JSON is malformed', async () => {
			mockFetch.mockResolvedValue({
				ok: true,
				status: 200,
				headers: { get: () => null },
				text: () => Promise.resolve('{malformed json}')
			} as unknown as Response);

			await expect(fetchPlaylist('p1')).rejects.toThrow('Failed to parse response JSON');
		});
	});

	describe('createPlaylist', () => {
		it('sends POST with { name } body', async () => {
			const detail = { id: 'p2', name: 'New', tracks: [] };
			mockFetch.mockResolvedValue(jsonResponse(detail, 201));

			const result = await createPlaylist('New');

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: 'New' })
			});
			expect(result).toEqual(detail);
		});
	});

	describe('updatePlaylist', () => {
		it('sends PUT with data body', async () => {
			const detail = { id: 'p1', name: 'Renamed' };
			mockFetch.mockResolvedValue(jsonResponse(detail));

			await updatePlaylist('p1', { name: 'Renamed' });

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ name: 'Renamed' })
			});
		});
	});

	describe('deletePlaylist', () => {
		it('calls DELETE on correct URL', async () => {
			mockFetch.mockResolvedValue(jsonResponse({ status: 'ok' }));
			await deletePlaylist('p1');
			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1', {
				method: 'DELETE'
			});
		});

		it('throws on non-ok response', async () => {
			mockFetch.mockResolvedValue(errorResponse(404, 'Not found'));
			await expect(deletePlaylist('p1')).rejects.toThrow('Not found');
		});
	});

	describe('addTracksToPlaylist', () => {
		it('sends POST with { tracks, position } and unwraps .tracks', async () => {
			const tracks = [{ track_name: 'Song', artist_name: 'Art', album_name: 'Alb', source_type: 'jellyfin' }];
			const responseTracks = [{ id: 't1', position: 0, track_name: 'Song' }];
			mockFetch.mockResolvedValue(jsonResponse({ tracks: responseTracks }, 201));

			const result = await addTracksToPlaylist('p1', tracks, 5);

			const call = mockFetch.mock.calls[0];
			expect(call[0]).toBe('/api/v1/playlists/p1/tracks');
			expect(call[1].method).toBe('POST');
			const body = JSON.parse(call[1].body);
			expect(body.tracks).toEqual(tracks);
			expect(body.position).toBe(5);
			expect(result).toEqual(responseTracks);
		});

		it('omits position when not provided', async () => {
			const tracks = [{ track_name: 'Song', artist_name: 'Art', album_name: 'Alb', source_type: 'jellyfin' }];
			mockFetch.mockResolvedValue(jsonResponse({ tracks: [] }, 201));

			await addTracksToPlaylist('p1', tracks);

			const body = JSON.parse(mockFetch.mock.calls[0][1].body);
			expect(body).not.toHaveProperty('position');
		});
	});

	describe('removeTrackFromPlaylist', () => {
		it('calls DELETE on correct URL', async () => {
			mockFetch.mockResolvedValue(jsonResponse({ status: 'ok' }));
			await removeTrackFromPlaylist('p1', 't1');
			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/t1', {
				method: 'DELETE'
			});
		});
	});

	describe('updatePlaylistTrack', () => {
		it('sends PATCH with data body', async () => {
			const track = { id: 't1', source_type: 'howler' };
			mockFetch.mockResolvedValue(jsonResponse(track));

			await updatePlaylistTrack('p1', 't1', { source_type: 'howler' });

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/t1', {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ source_type: 'howler' })
			});
		});
	});

	describe('reorderPlaylistTrack', () => {
		it('sends PATCH with { track_id, new_position }', async () => {
			mockFetch.mockResolvedValue(
				jsonResponse({ status: 'ok', message: 'Track reordered', actual_position: 3 })
			);

			const result = await reorderPlaylistTrack('p1', 't1', 3);

			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/reorder', {
				method: 'PATCH',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ track_id: 't1', new_position: 3 })
			});
			expect(result.actual_position).toBe(3);
		});
	});

	describe('uploadPlaylistCover', () => {
		it('sends FormData with cover_image key', async () => {
			mockFetch.mockResolvedValue(jsonResponse({ cover_url: '/covers/p1.jpg' }));
			const file = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });

			const result = await uploadPlaylistCover('p1', file);

			const call = mockFetch.mock.calls[0];
			expect(call[0]).toBe('/api/v1/playlists/p1/cover');
			expect(call[1].method).toBe('POST');
			const formData = call[1].body as FormData;
			expect(formData.get('cover_image')).toBeTruthy();
			expect(call[1].headers ?? {}).not.toHaveProperty('Content-Type');
			expect(result.cover_url).toBe('/covers/p1.jpg');
		});
	});

	describe('deletePlaylistCover', () => {
		it('calls DELETE on correct URL', async () => {
			mockFetch.mockResolvedValue(jsonResponse({ status: 'ok' }));
			await deletePlaylistCover('p1');
			expect(mockFetch).toHaveBeenCalledWith('/api/v1/playlists/p1/cover', {
				method: 'DELETE'
			});
		});
	});

	describe('queueItemToTrackData', () => {
		it('maps all fields correctly', () => {
			const item: QueueItem = {
				trackSourceId: 'vid-1',
				trackName: 'My Track',
				artistName: 'My Artist',
				trackNumber: 3,
				albumId: 'alb-1',
				albumName: 'My Album',
				coverUrl: '/cover.jpg',
				sourceType: 'jellyfin',
				artistId: 'art-1',
				streamUrl: '/stream/vid-1',
				format: 'aac',
				availableSources: ['jellyfin', 'howler'],
				duration: 240
			};

			const result = queueItemToTrackData(item);

			expect(result).toEqual({
				track_name: 'My Track',
				artist_name: 'My Artist',
				album_name: 'My Album',
				album_id: 'alb-1',
				artist_id: 'art-1',
				track_source_id: 'vid-1',
				cover_url: '/cover.jpg',
				source_type: 'jellyfin',
				available_sources: ['jellyfin', 'howler'],
				format: 'aac',
				track_number: 3,
				duration: 240
			});
		});

		it('handles optional/null fields correctly', () => {
			const item: QueueItem = {
				trackSourceId: '',
				trackName: 'Track',
				artistName: 'Artist',
				trackNumber: 1,
				albumId: '',
				albumName: 'Album',
				coverUrl: null,
				sourceType: 'howler'
			};

			const result = queueItemToTrackData(item);

			expect(result.album_id).toBeNull();
			expect(result.artist_id).toBeNull();
			expect(result.track_source_id).toBeNull();
			expect(result.cover_url).toBeNull();
			expect(result.available_sources).toBeNull();
			expect(result.format).toBeNull();
			expect(result.track_number).toBe(1);
			expect(result.duration).toBeNull();
		});

		it('excludes streamUrl from output', () => {
			const item: QueueItem = {
				trackSourceId: 'vid-1',
				trackName: 'Track',
				artistName: 'Artist',
				trackNumber: 1,
				albumId: 'alb-1',
				albumName: 'Album',
				coverUrl: null,
				sourceType: 'howler',
				streamUrl: '/stream/should-not-appear'
			};

			const result = queueItemToTrackData(item);

			expect(result).not.toHaveProperty('streamUrl');
			expect(result).not.toHaveProperty('stream_url');
		});
	});
});
