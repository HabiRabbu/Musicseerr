import type { AlbumTracksInfo } from '$lib/types';
import { api } from '$lib/api/client';

export async function fetchAlbumTracks(
	albumId: string,
	signal?: AbortSignal
): Promise<AlbumTracksInfo> {
	return api.global.get<AlbumTracksInfo>(`/api/v1/albums/${albumId}/tracks`, { signal });
}
