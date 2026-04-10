import { API } from '$lib/constants';
import { api, ApiError } from '$lib/api/client';
import type { PlexConnectionSettings } from '$lib/types';

let scrobbleEnabled: boolean | null = null;

async function loadScrobblePreference(): Promise<boolean> {
	if (scrobbleEnabled !== null) return scrobbleEnabled;
	try {
		const settings = await api.global.get<PlexConnectionSettings>(API.settingsPlex());
		scrobbleEnabled = settings.scrobble_to_plex ?? false;
	} catch {
		return false;
	}
	return scrobbleEnabled;
}

export function isPlexScrobbleEnabled(): boolean {
	return scrobbleEnabled ?? false;
}

export function resetPlexScrobblePreference(): void {
	scrobbleEnabled = null;
}

export async function reportPlexScrobble(ratingKey: string): Promise<void> {
	if (!(await loadScrobblePreference())) return;
	try {
		await api.global.post(API.stream.plexScrobble(ratingKey));
	} catch (e) {
		const detail = e instanceof ApiError ? String(e.status) : 'network error';
		console.warn(`[Plex] scrobble failed: ${detail}`);
	}
}

export async function reportPlexNowPlaying(ratingKey: string): Promise<void> {
	if (!(await loadScrobblePreference())) return;
	try {
		await api.global.post(API.stream.plexNowPlaying(ratingKey));
	} catch (e) {
		const detail = e instanceof ApiError ? String(e.status) : 'network error';
		console.warn(`[Plex] now-playing failed: ${detail}`);
	}
}
