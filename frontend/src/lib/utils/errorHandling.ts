import { isValidMbid } from '$lib/utils/formatting';
import { getApiUrl } from '$lib/api/api-utils';

export function isAbortError(error: unknown): boolean {
	return (
		(error instanceof DOMException && error.name === 'AbortError') ||
		(error instanceof Error && error.name === 'AbortError')
	);
}

export function getCoverUrl(coverUrl: string | null | undefined, albumId: string): string {
	if (isValidMbid(albumId)) {
		return getApiUrl(`/api/v1/covers/release-group/${albumId}?size=250`);
	}
	return coverUrl || getApiUrl(`/api/v1/covers/release-group/${albumId}?size=250`);
}
