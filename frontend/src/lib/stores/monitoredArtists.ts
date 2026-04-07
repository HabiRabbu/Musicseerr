import { writable, get } from 'svelte/store';

export interface PendingMonitor {
	monitored: boolean;
	autoDownload: boolean;
	timestamp: number;
}

const STORAGE_KEY = 'musicseerr_pending_artist_monitors';
const MAX_AGE_MS = 10 * 60 * 1000;

function loadFromStorage(): Map<string, PendingMonitor> {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (!raw) return new Map();
		const entries: [string, PendingMonitor][] = JSON.parse(raw);
		const now = Date.now();
		return new Map(entries.filter(([, v]) => now - v.timestamp < MAX_AGE_MS));
	} catch {
		return new Map();
	}
}

function persist(map: Map<string, PendingMonitor>): void {
	try {
		sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...map.entries()]));
	} catch {
		/* storage full or unavailable */
	}
}

function createMonitoredArtistsStore() {
	const { subscribe, update } = writable<Map<string, PendingMonitor>>(loadFromStorage());

	function addPendingMonitor(artistMbid: string, autoDownload: boolean): void {
		update((map) => {
			const next = new Map(map);
			next.set(artistMbid.toLowerCase(), {
				monitored: true,
				autoDownload,
				timestamp: Date.now()
			});
			persist(next);
			return next;
		});
	}

	function removePendingMonitor(artistMbid: string): void {
		update((map) => {
			const key = artistMbid.toLowerCase();
			if (!map.has(key)) return map;
			const next = new Map(map);
			next.delete(key);
			persist(next);
			return next;
		});
	}

	function getPendingMonitor(artistMbid: string | undefined | null): PendingMonitor | undefined {
		if (!artistMbid) return undefined;
		const entry = get({ subscribe }).get(artistMbid.toLowerCase());
		if (!entry) return undefined;
		if (Date.now() - entry.timestamp >= MAX_AGE_MS) return undefined;
		return entry;
	}

	return {
		subscribe,
		addPendingMonitor,
		removePendingMonitor,
		getPendingMonitor
	};
}

export const monitoredArtistsStore = createMonitoredArtistsStore();
