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
			removeTrack: (id: string, trackId: string) => `/api/v1/playlists/${id}/tracks/${trackId}`,
			removeTracks: (id: string) => `/api/v1/playlists/${id}/tracks/batch-remove`,
			updateTrack: (id: string, trackId: string) => `/api/v1/playlists/${id}/tracks/${trackId}`,
			reorderTrack: (id: string) => `/api/v1/playlists/${id}/tracks/reorder`,
			uploadCover: (id: string) => `/api/v1/playlists/${id}/cover`,
			deleteCover: (id: string) => `/api/v1/playlists/${id}/cover`,
			checkTracks: () => '/api/v1/playlists/check-tracks',
			resolveSources: (id: string) => `/api/v1/playlists/${id}/resolve-sources`
		}
	}
}));

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockPut = vi.fn();
const mockPatch = vi.fn();
const mockDelete = vi.fn();
const mockUpload = vi.fn();

vi.mock('$lib/api/client', () => ({
	api: {
		global: {
			get: (...args: unknown[]) => mockGet(...args),
			post: (...args: unknown[]) => mockPost(...args),
			put: (...args: unknown[]) => mockPut(...args),
			patch: (...args: unknown[]) => mockPatch(...args),
			delete: (...args: unknown[]) => mockDelete(...args),
			upload: (...args: unknown[]) => mockUpload(...args)
		}
	},
	ApiError: class ApiError extends Error {
		status: number;
		code: string;
		details: unknown;
		constructor(status: number, message: string, code = '', details: unknown = null) {
			super(message);
			this.name = 'ApiError';
			this.status = status;
			this.code = code;
			this.details = details;
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

beforeEach(() => {
	mockGet.mockReset();
	mockPost.mockReset();
	mockPut.mockReset();
	mockPatch.mockReset();
	mockDelete.mockReset();
	mockUpload.mockReset();
});

describe('playlists API client', () => {
	describe('fetchPlaylists', () => {
		it('calls api.global.get and unwraps .playlists', async () => {
			const playlists = [{ id: 'p1', name: 'My Playlist' }];
			mockGet.mockResolvedValue({ playlists });

			const result = await fetchPlaylists();

			expect(mockGet).toHaveBeenCalledWith('/api/v1/playlists');
			expect(result).toEqual(playlists);
		});

		it('throws on API error', async () => {
			mockGet.mockRejectedValue(new Error('Server error'));
			await expect(fetchPlaylists()).rejects.toThrow('Server error');
		});
	});

	describe('fetchPlaylist', () => {
		it('calls api.global.get with correct ID', async () => {
			const detail = { id: 'p1', name: 'Test', tracks: [] };
			mockGet.mockResolvedValue(detail);

			const result = await fetchPlaylist('p1');

			expect(mockGet).toHaveBeenCalledWith('/api/v1/playlists/p1', { signal: undefined });
			expect(result).toEqual(detail);
		});

		it('forwards AbortSignal when provided', async () => {
			const detail = { id: 'p1', name: 'Test', tracks: [] };
			const controller = new AbortController();
			mockGet.mockResolvedValue(detail);

			await fetchPlaylist('p1', { signal: controller.signal });

			expect(mockGet).toHaveBeenCalledWith('/api/v1/playlists/p1', {
				signal: controller.signal
			});
		});
	});

	describe('createPlaylist', () => {
		it('sends POST with { name } body', async () => {
			const detail = { id: 'p2', name: 'New', tracks: [] };
			mockPost.mockResolvedValue(detail);

			const result = await createPlaylist('New');

			expect(mockPost).toHaveBeenCalledWith('/api/v1/playlists', { name: 'New' });
			expect(result).toEqual(detail);
		});
	});

	describe('updatePlaylist', () => {
		it('sends PUT with data body', async () => {
			const detail = { id: 'p1', name: 'Renamed' };
			mockPut.mockResolvedValue(detail);

			await updatePlaylist('p1', { name: 'Renamed' });

			expect(mockPut).toHaveBeenCalledWith('/api/v1/playlists/p1', { name: 'Renamed' });
		});
	});

	describe('deletePlaylist', () => {
		it('calls api.global.delete on correct URL', async () => {
			mockDelete.mockResolvedValue(undefined);
			await deletePlaylist('p1');
			expect(mockDelete).toHaveBeenCalledWith('/api/v1/playlists/p1');
		});

		it('throws on error', async () => {
			mockDelete.mockRejectedValue(new Error('Not found'));
			await expect(deletePlaylist('p1')).rejects.toThrow('Not found');
		});
	});

	describe('addTracksToPlaylist', () => {
		it('sends POST with { tracks, position } and unwraps .tracks', async () => {
			const tracks = [
				{ track_name: 'Song', artist_name: 'Art', album_name: 'Alb', source_type: 'jellyfin' }
			];
			const responseTracks = [{ id: 't1', position: 0, track_name: 'Song' }];
			mockPost.mockResolvedValue({ tracks: responseTracks });

			const result = await addTracksToPlaylist('p1', tracks, 5);

			const call = mockPost.mock.calls[0];
			expect(call[0]).toBe('/api/v1/playlists/p1/tracks');
			expect(call[1].tracks).toEqual(tracks);
			expect(call[1].position).toBe(5);
			expect(result).toEqual(responseTracks);
		});

		it('omits position when not provided', async () => {
			const tracks = [
				{ track_name: 'Song', artist_name: 'Art', album_name: 'Alb', source_type: 'jellyfin' }
			];
			mockPost.mockResolvedValue({ tracks: [] });

			await addTracksToPlaylist('p1', tracks);

			const body = mockPost.mock.calls[0][1];
			expect(body).not.toHaveProperty('position');
		});
	});

	describe('removeTrackFromPlaylist', () => {
		it('calls api.global.delete on correct URL', async () => {
			mockDelete.mockResolvedValue(undefined);
			await removeTrackFromPlaylist('p1', 't1');
			expect(mockDelete).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/t1');
		});
	});

	describe('updatePlaylistTrack', () => {
		it('sends PATCH with data body', async () => {
			const track = { id: 't1', source_type: 'local' };
			mockPatch.mockResolvedValue(track);

			await updatePlaylistTrack('p1', 't1', { source_type: 'local' });

			expect(mockPatch).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/t1', {
				source_type: 'local'
			});
		});
	});

	describe('reorderPlaylistTrack', () => {
		it('sends PATCH with { track_id, new_position }', async () => {
			mockPatch.mockResolvedValue({ status: 'ok', message: 'Track reordered', actual_position: 3 });

			const result = await reorderPlaylistTrack('p1', 't1', 3);

			expect(mockPatch).toHaveBeenCalledWith('/api/v1/playlists/p1/tracks/reorder', {
				track_id: 't1',
				new_position: 3
			});
			expect(result.actual_position).toBe(3);
		});
	});

	describe('uploadPlaylistCover', () => {
		it('sends FormData via api.global.upload', async () => {
			mockUpload.mockResolvedValue({ cover_url: '/covers/p1.jpg' });
			const file = new File(['img'], 'cover.jpg', { type: 'image/jpeg' });

			const result = await uploadPlaylistCover('p1', file);

			const call = mockUpload.mock.calls[0];
			expect(call[0]).toBe('/api/v1/playlists/p1/cover');
			const formData = call[1] as FormData;
			expect(formData.get('cover_image')).toBeTruthy();
			expect(result.cover_url).toBe('/covers/p1.jpg');
		});
	});

	describe('deletePlaylistCover', () => {
		it('calls api.global.delete on correct URL', async () => {
			mockDelete.mockResolvedValue(undefined);
			await deletePlaylistCover('p1');
			expect(mockDelete).toHaveBeenCalledWith('/api/v1/playlists/p1/cover');
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
				availableSources: ['jellyfin', 'local'],
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
				available_sources: ['jellyfin', 'local'],
				format: 'aac',
				track_number: 3,
				disc_number: null,
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
				sourceType: 'local'
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
				sourceType: 'local',
				streamUrl: '/stream/should-not-appear'
			};

			const result = queueItemToTrackData(item);

			expect(result).not.toHaveProperty('streamUrl');
			expect(result).not.toHaveProperty('stream_url');
		});
	});
});
