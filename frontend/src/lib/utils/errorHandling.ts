import { MESSAGES } from '$lib/constants';

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
