import { API } from '$lib/constants';
import type { QueueItem } from '$lib/player/types';

export interface PlaylistTrack {
	id: string;
	position: number;
	track_name: string;
	artist_name: string;
	album_name: string;
	album_id: string | null;
	artist_id: string | null;
	track_source_id: string | null;
	cover_url: string | null;
	source_type: string;
	available_sources: string[] | null;
	format: string | null;
	track_number: number | null;
	duration: number | null;
	created_at: string;
}

export interface PlaylistSummary {
	id: string;
	name: string;
	track_count: number;
	total_duration: number | null;
	cover_urls: string[];
	custom_cover_url: string | null;
	created_at: string;
	updated_at: string;
}

export interface PlaylistDetail extends PlaylistSummary {
	tracks: PlaylistTrack[];
}

export interface TrackData {
	track_name: string;
	artist_name: string;
	album_name: string;
	album_id?: string | null;
	artist_id?: string | null;
	track_source_id?: string | null;
	cover_url?: string | null;
	source_type: string;
	available_sources?: string[] | null;
	format?: string | null;
	track_number?: number | null;
	duration?: number | null;
}

export function queueItemToTrackData(item: QueueItem): TrackData {
	return {
		track_name: item.trackName,
		artist_name: item.artistName,
		album_name: item.albumName,
		album_id: item.albumId || null,
		artist_id: item.artistId || null,
		track_source_id: item.trackSourceId || null,
		cover_url: item.coverUrl,
		source_type: item.sourceType,
		available_sources: item.availableSources ?? null,
		format: item.format ?? null,
		track_number: item.trackNumber ?? null,
		duration: item.duration ?? null
	};
}

async function handleResponse<T = void>(res: Response): Promise<T> {
	if (!res.ok) {
		const text = await res.text().catch(() => '');
		throw new Error(text || `Request failed with status ${res.status}`);
	}
	if (res.status === 204 || res.headers.get('content-length') === '0') {
		return undefined as T;
	}
	const text = await res.text().catch(() => '');
	if (text.trim() === '') {
		return undefined as T;
	}

	try {
		return JSON.parse(text) as T;
	} catch {
		throw new Error('Failed to parse response JSON');
	}
}

export async function fetchPlaylists(): Promise<PlaylistSummary[]> {
	const res = await fetch(API.playlists.list());
	const data = await handleResponse<{ playlists: PlaylistSummary[] }>(res);
	return data.playlists;
}

export async function fetchPlaylist(
	id: string,
	options?: { signal?: AbortSignal }
): Promise<PlaylistDetail> {
	const res = options?.signal
		? await fetch(API.playlists.detail(id), { signal: options.signal })
		: await fetch(API.playlists.detail(id));
	return handleResponse<PlaylistDetail>(res);
}

export async function createPlaylist(name: string): Promise<PlaylistDetail> {
	const res = await fetch(API.playlists.create(), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ name })
	});
	return handleResponse<PlaylistDetail>(res);
}

export async function updatePlaylist(
	id: string,
	data: { name?: string }
): Promise<PlaylistDetail> {
	const res = await fetch(API.playlists.update(id), {
		method: 'PUT',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	return handleResponse<PlaylistDetail>(res);
}

export async function deletePlaylist(id: string): Promise<void> {
	const res = await fetch(API.playlists.delete(id), { method: 'DELETE' });
	await handleResponse(res);
}

export async function addTracksToPlaylist(
	id: string,
	tracks: TrackData[],
	position?: number
): Promise<PlaylistTrack[]> {
	const body: { tracks: TrackData[]; position?: number } = { tracks };
	if (position != null) body.position = position;
	const res = await fetch(API.playlists.addTracks(id), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(body)
	});
	const data = await handleResponse<{ tracks: PlaylistTrack[] }>(res);
	return data.tracks;
}

export async function removeTrackFromPlaylist(
	id: string,
	trackId: string
): Promise<void> {
	const res = await fetch(API.playlists.removeTrack(id, trackId), {
		method: 'DELETE'
	});
	await handleResponse(res);
}

export async function updatePlaylistTrack(
	id: string,
	trackId: string,
	data: { source_type?: string; available_sources?: string[] }
): Promise<PlaylistTrack> {
	const res = await fetch(API.playlists.updateTrack(id, trackId), {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(data)
	});
	return handleResponse<PlaylistTrack>(res);
}

export async function reorderPlaylistTrack(
	id: string,
	trackId: string,
	newPosition: number
): Promise<{ actual_position: number }> {
	const res = await fetch(API.playlists.reorderTrack(id), {
		method: 'PATCH',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ track_id: trackId, new_position: newPosition })
	});
	return handleResponse<{ actual_position: number }>(res);
}

export async function uploadPlaylistCover(
	id: string,
	file: File
): Promise<{ cover_url: string }> {
	const formData = new FormData();
	formData.append('cover_image', file);
	const res = await fetch(API.playlists.uploadCover(id), {
		method: 'POST',
		body: formData
	});
	return handleResponse<{ cover_url: string }>(res);
}

export async function deletePlaylistCover(id: string): Promise<void> {
	const res = await fetch(API.playlists.deleteCover(id), { method: 'DELETE' });
	await handleResponse(res);
}

export async function checkTrackMembership(
	tracks: { track_name: string; artist_name: string; album_name: string }[]
): Promise<Record<string, number[]>> {
	const res = await fetch(API.playlists.checkTracks(), {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify({ tracks })
	});
	const data = await handleResponse<{ membership: Record<string, number[]> }>(res);
	return data.membership;
}

export async function resolvePlaylistSources(
	id: string
): Promise<Record<string, string[]>> {
	const res = await fetch(API.playlists.resolveSources(id), { method: 'POST' });
	const data = await handleResponse<{ sources: Record<string, string[]> }>(res);
	return data.sources;
}
