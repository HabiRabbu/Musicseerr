import { API } from '$lib/constants';
import { integrationStore } from '$lib/stores/integration';
import { get } from 'svelte/store';
import { SvelteMap, SvelteSet } from 'svelte/reactivity';
import type {
	NowPlayingSession,
	JellyfinSessionInfo,
	JellyfinSessionsResponse,
	NavidromeNowPlayingEntry,
	NavidromeNowPlayingResponse,
	PlexSessionInfo,
	PlexSessionsResponse
} from '$lib/types';

const POLL_INTERVAL_MS = 3_000;
const STALE_SESSION_EXPIRY_MS = 30_000;
const STALE_PROGRESS_THRESHOLD_MS = POLL_INTERVAL_MS * 2.5;
const MAX_INTERPOLATION_ADVANCE_MS = POLL_INTERVAL_MS * 3;
const FROZEN_BASIS_MS = 15_000;

type SourceKey = 'jellyfin' | 'navidrome' | 'plex';
type InterpolationBasis = { serverProgress: number; updatedAt: number };

function jellyfinToSession(s: JellyfinSessionInfo): NowPlayingSession {
	return {
		id: s.session_id,
		user_name: s.user_name,
		track_name: s.track_name,
		artist_name: s.artist_name,
		album_name: s.album_name,
		cover_url: s.cover_url,
		device_name: s.device_name,
		is_paused: s.is_paused,
		source: 'jellyfin',
		progress_ms: s.position_seconds * 1000,
		duration_ms: s.duration_seconds * 1000,
		audio_codec: s.audio_codec,
		bitrate: s.bitrate
	};
}

function navidromeToSession(e: NavidromeNowPlayingEntry): NowPlayingSession {
	const progressMs =
		e.estimated_position_seconds != null && e.estimated_position_seconds > 0
			? e.estimated_position_seconds * 1000
			: e.minutes_ago > 0
				? Math.max(0, e.duration_seconds * 1000 - e.minutes_ago * 60_000)
				: 0;
	return {
		id: `${e.user_name}-${e.player_name}-${e.album_id}-${e.track_name}`,
		user_name: e.user_name,
		track_name: e.track_name,
		artist_name: e.artist_name,
		album_name: e.album_name,
		cover_url: e.cover_art_id ? `/api/v1/navidrome/cover/${e.cover_art_id}` : '',
		device_name: e.player_name,
		is_paused: false,
		source: 'navidrome',
		progress_ms: progressMs,
		duration_ms: e.duration_seconds * 1000
	};
}

function plexToSession(s: PlexSessionInfo): NowPlayingSession {
	return {
		id: s.session_id,
		user_name: s.user_name,
		track_name: s.track_title,
		artist_name: s.artist_name,
		album_name: s.album_name,
		cover_url: s.cover_url,
		device_name: s.player_device,
		is_paused: s.player_state === 'paused',
		source: 'plex',
		progress_ms: s.progress_ms,
		duration_ms: s.duration_ms,
		audio_codec: s.audio_codec,
		bitrate: s.bitrate
	};
}

const FETCH_FAILED = Symbol('fetch_failed');

function createNowPlayingStore() {
	let sessions = $state<NowPlayingSession[]>([]);
	let pollTimer: ReturnType<typeof setInterval> | undefined;
	let tickTimer: ReturnType<typeof setInterval> | undefined;
	let running = false;

	const lastGoodSessions = new SvelteMap<SourceKey, NowPlayingSession[]>();
	const interpBasis = new SvelteMap<string, InterpolationBasis>();

	const activeSessions = $derived(sessions.filter((s) => !s.is_paused));
	const primarySession = $derived(activeSessions[0] ?? sessions[0] ?? null);

	async function fetchSource<T>(
		url: string,
		mapper: (data: T) => NowPlayingSession[],
		source: SourceKey
	): Promise<NowPlayingSession[] | typeof FETCH_FAILED> {
		try {
			const r = await fetch(url);
			if (!r.ok) return FETCH_FAILED;
			const data: T = await r.json();
			const mapped = mapper(data);
			lastGoodSessions.set(source, mapped);
			return mapped;
		} catch {
			return FETCH_FAILED;
		}
	}

	async function fetchAll() {
		if (typeof document !== 'undefined' && document.hidden) return;

		const integrations = get(integrationStore);
		const fetches: Promise<{
			source: SourceKey;
			result: NowPlayingSession[] | typeof FETCH_FAILED;
		}>[] = [];

		if (integrations.jellyfin) {
			fetches.push(
				fetchSource<JellyfinSessionsResponse>(
					API.jellyfinLibrary.sessions(),
					(d) => (d?.sessions ?? []).map(jellyfinToSession),
					'jellyfin'
				).then((result) => ({ source: 'jellyfin' as SourceKey, result }))
			);
		}
		if (integrations.navidrome) {
			fetches.push(
				fetchSource<NavidromeNowPlayingResponse>(
					API.navidromeLibrary.nowPlaying(),
					(d) => (d?.entries ?? []).map(navidromeToSession),
					'navidrome'
				).then((result) => ({ source: 'navidrome' as SourceKey, result }))
			);
		}
		if (integrations.plex) {
			fetches.push(
				fetchSource<PlexSessionsResponse>(
					API.plexLibrary.sessions(),
					(d) => (d?.sessions ?? []).map(plexToSession),
					'plex'
				).then((result) => ({ source: 'plex' as SourceKey, result }))
			);
		}

		if (fetches.length === 0) {
			sessions = [];
			return;
		}

		const results = await Promise.all(fetches);
		const now = Date.now();
		const incoming: NowPlayingSession[] = [];

		for (const { source, result } of results) {
			if (result === FETCH_FAILED) {
				const stale = lastGoodSessions.get(source);
				if (stale && stale.length > 0) {
					const basis = interpBasis.get(stale[0].id);
					if (!basis || now - basis.updatedAt < STALE_SESSION_EXPIRY_MS) {
						incoming.push(...stale);
					}
				}
			} else {
				incoming.push(...result);
			}
		}

		const newIds = new SvelteSet<string>();
		for (const s of incoming) {
			newIds.add(s.id);
			const prev = interpBasis.get(s.id);
			if (s.progress_ms != null) {
				if (!prev || prev.serverProgress !== s.progress_ms) {
					interpBasis.set(s.id, { serverProgress: s.progress_ms, updatedAt: now });
				}
			}
		}
		for (const key of interpBasis.keys()) {
			if (!newIds.has(key)) interpBasis.delete(key);
		}

		for (const s of incoming) {
			if (s.is_paused) continue;
			const basis = interpBasis.get(s.id);
			if (basis && now - basis.updatedAt > STALE_PROGRESS_THRESHOLD_MS) {
				s.is_paused = true;
			}
		}

		sessions = incoming;
	}

	function tick() {
		if (typeof document !== 'undefined' && document.hidden) return;
		const now = Date.now();
		const updated = sessions.map((s) => {
			if (s.is_paused || !s.duration_ms || s.progress_ms == null) return s;
			const basis = interpBasis.get(s.id);
			if (!basis) {
				const next = Math.min(s.progress_ms + 1000, s.duration_ms);
				return next === s.progress_ms ? s : { ...s, progress_ms: next };
			}
			const basisAge = now - basis.updatedAt;
			if (basisAge > FROZEN_BASIS_MS) return s;
			const elapsed = Math.min(basisAge, MAX_INTERPOLATION_ADVANCE_MS);
			const interpolated = Math.min(basis.serverProgress + elapsed, s.duration_ms);
			if (interpolated === s.progress_ms) return s;
			return { ...s, progress_ms: interpolated };
		});
		sessions = updated;
	}

	function start() {
		if (running) return;
		running = true;
		fetchAll();
		pollTimer = setInterval(fetchAll, POLL_INTERVAL_MS);
		tickTimer = setInterval(tick, 1000);
		if (typeof document !== 'undefined') {
			document.addEventListener('visibilitychange', onVisibility);
		}
	}

	function stop() {
		running = false;
		if (pollTimer) {
			clearInterval(pollTimer);
			pollTimer = undefined;
		}
		if (tickTimer) {
			clearInterval(tickTimer);
			tickTimer = undefined;
		}
		if (typeof document !== 'undefined') {
			document.removeEventListener('visibilitychange', onVisibility);
		}
	}

	function onVisibility() {
		if (!document.hidden && running) {
			fetchAll();
		}
	}

	function isSourcePlaying(source: SourceKey): boolean {
		return sessions.some((s) => s.source === source && !s.is_paused);
	}

	function sourceHasSessions(source: SourceKey): boolean {
		return sessions.some((s) => s.source === source);
	}

	function sessionsForSource(source: SourceKey): NowPlayingSession[] {
		return sessions.filter((s) => s.source === source);
	}

	return {
		get sessions() {
			return sessions;
		},
		get activeSessions() {
			return activeSessions;
		},
		get primarySession() {
			return primarySession;
		},
		start,
		stop,
		refresh: fetchAll,
		isSourcePlaying,
		sourceHasSessions,
		sessionsForSource
	};
}

export const nowPlayingStore = createNowPlayingStore();
