import { libraryStore } from '$lib/stores/library';
import { API } from '$lib/constants';

export interface AlbumRemoveResult {
	success: boolean;
	artist_removed: boolean;
	artist_name?: string | null;
	error?: string;
}

export interface AlbumRemovePreviewResult {
	success: boolean;
	artist_will_be_removed: boolean;
	artist_name?: string | null;
	error?: string;
}

export async function getAlbumRemovePreview(
	musicbrainzId: string
): Promise<AlbumRemovePreviewResult> {
	try {
		const res = await fetch(API.library.removeAlbumPreview(musicbrainzId));

		if (res.ok) {
			const data = await res.json();
			return {
				success: true,
				artist_will_be_removed: data.artist_will_be_removed ?? false,
				artist_name: data.artist_name ?? null
			};
		}

		const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
		return {
			success: false,
			artist_will_be_removed: false,
			error: errorData.detail || 'Failed to load removal preview'
		};
	} catch {
		return {
			success: false,
			artist_will_be_removed: false,
			error: 'Network error occurred'
		};
	}
}

export async function removeAlbum(
	musicbrainzId: string,
	deleteFiles: boolean = false
): Promise<AlbumRemoveResult> {
	try {
		const url = `${API.library.removeAlbum(musicbrainzId)}?delete_files=${deleteFiles}`;
		const res = await fetch(url, { method: 'DELETE' });

		if (res.ok) {
			const data = await res.json();
			libraryStore.removeMbid(musicbrainzId);
			return {
				success: true,
				artist_removed: data.artist_removed ?? false,
				artist_name: data.artist_name ?? null
			};
		}

		const errorData = await res.json().catch(() => ({ detail: 'Unknown error' }));
		return {
			success: false,
			artist_removed: false,
			error: errorData.detail || 'Failed to remove album'
		};
	} catch {
		return {
			success: false,
			artist_removed: false,
			error: 'Network error occurred'
		};
	}
}
