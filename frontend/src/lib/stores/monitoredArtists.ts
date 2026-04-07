import { writable, get } from 'svelte/store';

export interface PendingMonitor {
	monitored: boolean;
	autoDownload: boolean;
	timestamp: number;
}

const STORAGE_KEY = 'musicseerr_pending_artist_monitors';
const MAX_AGE_MS = 10 * 60 * 1000;

export function getValidPendingMonitor(
	entries: Map<string, PendingMonitor>,
	artistMbid: string | undefined | null,
	now = Date.now()
): PendingMonitor | undefined {
	if (!artistMbid) return undefined;
	const entry = entries.get(artistMbid.toLowerCase());
	if (!entry) return undefined;
	if (now - entry.timestamp >= MAX_AGE_MS) return undefined;
	return entry;
}

function pruneExpiredPendingMonitors(
	entries: Map<string, PendingMonitor>,
	now = Date.now()
): Map<string, PendingMonitor> {
	return new Map([...entries.entries()].filter(([, entry]) => now - entry.timestamp < MAX_AGE_MS));
}

function loadFromStorage(): Map<string, PendingMonitor> {
	try {
		const raw = sessionStorage.getItem(STORAGE_KEY);
		if (!raw) return new Map();
		const entries: [string, PendingMonitor][] = JSON.parse(raw);
		return pruneExpiredPendingMonitors(new Map(entries));
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
	const initialEntries = loadFromStorage();
	const { subscribe, update } = writable<Map<string, PendingMonitor>>(initialEntries);
	let expiryTimeout: ReturnType<typeof setTimeout> | null = null;

	function clearExpiryTimeout(): void {
		if (expiryTimeout) {
			clearTimeout(expiryTimeout);
			expiryTimeout = null;
		}
	}

	function scheduleExpiry(entries: Map<string, PendingMonitor>): void {
		clearExpiryTimeout();
		let nextExpiryAt: number | null = null;
		for (const entry of entries.values()) {
			const expiresAt = entry.timestamp + MAX_AGE_MS;
			if (nextExpiryAt === null || expiresAt < nextExpiryAt) {
				nextExpiryAt = expiresAt;
			}
		}
		if (nextExpiryAt === null) return;
		const delay = Math.max(nextExpiryAt - Date.now(), 0);
		expiryTimeout = setTimeout(() => {
			update((map) => {
				const next = pruneExpiredPendingMonitors(map);
				if (next.size !== map.size) {
					persist(next);
				}
				scheduleExpiry(next);
				return next.size === map.size ? map : next;
			});
		}, delay);
	}

	function addPendingMonitor(artistMbid: string, autoDownload: boolean): void {
		update((map) => {
			const next = new Map(map);
			next.set(artistMbid.toLowerCase(), {
				monitored: true,
				autoDownload,
				timestamp: Date.now()
			});
			persist(next);
			scheduleExpiry(next);
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
			scheduleExpiry(next);
			return next;
		});
	}

	function getPendingMonitor(artistMbid: string | undefined | null): PendingMonitor | undefined {
		return getValidPendingMonitor(get({ subscribe }), artistMbid);
	}

	scheduleExpiry(initialEntries);

	return {
		subscribe,
		addPendingMonitor,
		removePendingMonitor,
		getPendingMonitor
	};
}

export const monitoredArtistsStore = createMonitoredArtistsStore();
