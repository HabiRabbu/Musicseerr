import { API } from '$lib/constants';

type PlaybackSessionResult = {
	play_session_id: string;
	item_id: string;
};

type StartSessionPayload = {
	play_session_id?: string;
};

export async function startSession(itemId: string, playSessionId?: string): Promise<string> {
	const payload: StartSessionPayload | undefined = playSessionId
		? { play_session_id: playSessionId }
		: undefined;

	const res = await fetch(API.stream.jellyfinStart(itemId), {
		method: 'POST',
		headers: payload ? { 'Content-Type': 'application/json' } : undefined,
		body: payload ? JSON.stringify(payload) : undefined
	});
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
): Promise<boolean> {
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
			return false;
		}
		return true;
	} catch {
		console.warn('[Jellyfin] progress report failed: network error');
		return false;
	}
}

export async function reportStop(
	itemId: string,
	playSessionId: string,
	positionSeconds: number
): Promise<boolean> {
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
			return false;
		}
		return true;
	} catch {
		// Stop reporting is non-fatal — swallow network errors
		return false;
	}
}
