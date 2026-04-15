import { libraryStore } from '$lib/stores/library';
import { api } from '$lib/api/client';

export async function toggleAlbumMonitored(mbid: string, monitored: boolean): Promise<void> {
	await api.global.put(`/api/v1/albums/${mbid}/monitor`, { monitored });
	libraryStore.setMonitored(mbid, monitored);
}
