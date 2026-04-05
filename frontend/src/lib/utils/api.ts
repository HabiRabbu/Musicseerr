import { env } from '$env/dynamic/public';

/**
 * Normalizes an API path by prepending the PUBLIC_API_URL if it's set.
 * Useful for <img> src tags, Background image URLs, and other places where
 * the API client isn't automatically resolving the absolute URL.
 *
 * @param path The API path (e.g., '/api/v1/covers/...')
 * @returns The fully qualified API URL or the original path if PUBLIC_API_URL is unset.
 */
export function getApiUrl(path: string): string {
	if (!path.startsWith('/')) {
		return path;
	}

	if (env.PUBLIC_API_URL) {
		const baseUrl = env.PUBLIC_API_URL.replace(/\/$/, '');
		return `${baseUrl}${path}`;
	}

	return path;
}
