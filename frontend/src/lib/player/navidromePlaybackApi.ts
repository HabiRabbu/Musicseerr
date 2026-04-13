import { API } from '$lib/constants';
import { api } from '$lib/api/client';

export async function reportNavidromeScrobble(itemId: string): Promise<void> {
	try {
		await api.global.post<{ status: string }>(API.stream.navidromeScrobble(itemId));
	} catch {
		// best-effort scrobble
	}
}

export async function reportNavidromeNowPlaying(itemId: string): Promise<void> {
	try {
		await api.global.post(API.stream.navidromeNowPlaying(itemId));
	} catch {
		// best-effort now-playing report
	}
}

export async function reportNavidromeStopped(itemId: string): Promise<void> {
	try {
		await api.global.post(API.stream.navidromeStopped(itemId));
	} catch (e) {
		const detail = e instanceof ApiError ? String(e.status) : 'network error';
		console.warn(`[Navidrome] stopped report failed: ${detail}`);
	}
}
