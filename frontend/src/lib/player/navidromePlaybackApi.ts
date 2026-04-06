import { API } from '$lib/constants';
import { api, ApiError } from '$lib/api/client';

export async function reportNavidromeScrobble(itemId: string): Promise<void> {
	try {
		const body = await api.global.post<{ status: string }>(API.stream.navidromeScrobble(itemId));
		if (body.status !== 'ok') {
			console.warn('[Navidrome] scrobble reported error');
		}
	} catch (e) {
		const detail = e instanceof ApiError ? String(e.status) : 'network error';
		console.warn(`[Navidrome] scrobble failed: ${detail}`);
	}
}

export async function reportNavidromeNowPlaying(itemId: string): Promise<void> {
	try {
		await api.global.post(API.stream.navidromeNowPlaying(itemId));
	} catch (e) {
		const detail = e instanceof ApiError ? String(e.status) : 'network error';
		console.warn(`[Navidrome] now-playing failed: ${detail}`);
	}
}
