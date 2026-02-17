import { API } from '$lib/constants';

type PlaybackSessionResult = {
	play_session_id: string;
	item_id: string;
};

export async function startSession(itemId: string): Promise<string> {
	const res = await fetch(API.stream.jellyfinStart(itemId), { method: 'POST' });
	if (!res.ok) {
		const detail = await res.text().catch(() => 'Unknown error');
		throw new Error(`Failed to start Jellyfin playback session: ${res.status} ${detail}`);
	}
	const data: PlaybackSessionResult = await res.json();
	return data.play_session_id;
}

export async function reportProgress(
	itemId: string,
	playSessionId: string,
	positionSeconds: number,
	isPaused: boolean
): Promise<void> {
	try {
		const res = await fetch(API.stream.jellyfinProgress(itemId), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				play_session_id: playSessionId,
				position_seconds: positionSeconds,
				is_paused: isPaused
			})
		});
		if (!res.ok) {
			console.warn(`[Jellyfin] progress report failed: ${res.status}`);
		}
	} catch {
		console.warn('[Jellyfin] progress report failed: network error');
	}
}

export async function reportStop(
	itemId: string,
	playSessionId: string,
	positionSeconds: number
): Promise<void> {
	try {
		const res = await fetch(API.stream.jellyfinStop(itemId), {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				play_session_id: playSessionId,
				position_seconds: positionSeconds
			})
		});
		if (!res.ok) {
			console.warn(`[Jellyfin] stop report failed: ${res.status}`);
		}
	} catch {
		// Stop reporting is non-fatal — swallow network errors
	}
}
