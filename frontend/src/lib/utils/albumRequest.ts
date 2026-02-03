import { errorModal } from '$lib/stores/errorModal';
import { libraryStore } from '$lib/stores/library';

export interface AlbumRequestResult {
	success: boolean;
	error?: string;
}

export async function requestAlbum(musicbrainzId: string): Promise<AlbumRequestResult> {
	try {
		const res = await fetch('/api/request', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ musicbrainz_id: musicbrainzId })
		});

		if (res.ok) {
			libraryStore.addRequested(musicbrainzId);
			return { success: true };
		}

		const errorData = await res.json();
		const errorDetail = errorData.detail || 'Unknown error';

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
	} catch (e) {
		errorModal.show('Request Failed', 'Network error occurred', '');
		return { success: false, error: 'Network error occurred' };
	}
}

export function createRequestHandler() {
	let requestingIds = new Set<string>();

	function isRequesting(id: string): boolean {
		return requestingIds.has(id);
	}

	function getRequestingIds(): Set<string> {
		return requestingIds;
	}

	async function handleRequest(
		id: string,
		options?: {
			onSuccess?: () => void;
			onError?: (error: string) => void;
			updateLocalState?: () => void;
		}
	): Promise<boolean> {
		if (requestingIds.has(id)) return false;

		requestingIds.add(id);
		requestingIds = requestingIds;

		try {
			const result = await requestAlbum(id);

			if (result.success) {
				options?.updateLocalState?.();
				options?.onSuccess?.();
				return true;
			} else {
				options?.onError?.(result.error || 'Unknown error');
				return false;
			}
		} finally {
			requestingIds.delete(id);
			requestingIds = requestingIds;
		}
	}

	return {
		handleRequest,
		isRequesting,
		getRequestingIds
	};
}
