import { MESSAGES } from '$lib/constants';
import { isValidMbid } from '$lib/utils/formatting';

export function handleFetchError(error: unknown, fallback: string): string | null {
	if (error instanceof Error && error.name === 'AbortError') return null;
	return error instanceof Error ? error.message : fallback;
}

export function isAbortError(error: unknown): boolean {
	return error instanceof Error && error.name === 'AbortError';
}

export function getErrorMessage(error: unknown, fallback: string = MESSAGES.ERRORS.NETWORK): string {
	if (error instanceof Error) {
		return error.message;
	}
	return fallback;
}

export async function throwOnApiError(res: Response, fallbackMessage: string): Promise<void> {
	if (res.ok) return;
	const err = await res.json().catch(() => null);
	throw new Error(err?.detail?.message || err?.detail || fallbackMessage);
}

export function getCoverUrl(coverUrl: string | null | undefined, albumId: string): string {
	if (isValidMbid(albumId)) {
		return `/api/covers/release-group/${albumId}?size=250`;
	}
	return coverUrl || `/api/covers/release-group/${albumId}?size=250`;
}
