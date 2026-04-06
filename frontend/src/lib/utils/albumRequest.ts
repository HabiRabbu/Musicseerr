import { errorModal } from '$lib/stores/errorModal';
import { libraryStore } from '$lib/stores/library';
import { notifyRequestCountChanged } from '$lib/utils/requestsApi';
import { api, ApiError } from '$lib/api/client';

export type AlbumRequestResult = {
	success: boolean;
	error?: string;
};

export type AlbumRequestContext = {
	artist?: string;
	album?: string;
	year?: number | null;
	artistMbid?: string;
	monitorArtist?: boolean;
	autoDownloadArtist?: boolean;
};

export async function requestAlbum(
	musicbrainzId: string,
	context?: AlbumRequestContext
): Promise<AlbumRequestResult> {
	try {
		await api.global.post('/api/v1/requests/new', {
			musicbrainz_id: musicbrainzId,
			artist: context?.artist ?? undefined,
			album: context?.album ?? undefined,
			year: context?.year ?? undefined,
			artist_mbid: context?.artistMbid ?? undefined,
			monitor_artist: context?.monitorArtist ?? false,
			auto_download_artist: context?.autoDownloadArtist ?? false
		});

		libraryStore.addRequested(musicbrainzId);
		notifyRequestCountChanged();
		return { success: true };
	} catch (e) {
		if (e instanceof ApiError) {
			const errorDetail = e.message || 'Unknown error';

			if (errorDetail.includes('Metadata Profile') || errorDetail.includes('Cannot add this')) {
				const albumTypeMatch = errorDetail.match(/Cannot add this (\w+)/);
				const albumType = albumTypeMatch ? albumTypeMatch[1] : 'release';

				errorModal.show(
					`Cannot Add ${albumType}`,
					errorDetail,
					'Go to Lidarr -> Settings -> Profiles -> Metadata Profiles, and enable the appropriate release types in your active profile. After enabling, refresh the artist in Lidarr.'
				);
			} else {
				errorModal.show('Request Failed', errorDetail, '');
			}

			return { success: false, error: errorDetail };
		}
		errorModal.show('Request Failed', 'Network error occurred', '');
		return { success: false, error: 'Network error occurred' };
	}
}
