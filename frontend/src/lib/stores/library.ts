import { writable, get } from 'svelte/store';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';
import { api } from '$lib/api/client';

export interface LibraryState {
	mbidSet: Set<string>;
	requestedSet: Set<string>;
	monitoredSet: Set<string>;
	loading: boolean;
	lastUpdated: number | null;
	initialized: boolean;
}

const initialState: LibraryState = {
	mbidSet: new Set(),
	requestedSet: new Set(),
	monitoredSet: new Set(),
	loading: false,
	lastUpdated: null,
	initialized: false
};

type LibraryCacheData = {
	mbids: string[];
	requested: string[];
	monitored: string[];
};

function createLibraryStore() {
	const { subscribe, update } = writable<LibraryState>(initialState);
	const cache = createLocalStorageCache<LibraryCacheData | string[]>(
		CACHE_KEYS.LIBRARY_MBIDS,
		CACHE_TTL.LIBRARY
	);

	function normalizeCachedData(data: LibraryCacheData | string[]): LibraryCacheData {
		if (Array.isArray(data)) {
			return { mbids: data, requested: [], monitored: [] };
		}
		return {
			mbids: data.mbids ?? [],
			requested: data.requested ?? [],
			monitored: data.monitored ?? []
		};
	}

	function persistState(
		mbidSet: Set<string>,
		requestedSet: Set<string>,
		monitoredSet: Set<string>
	) {
		cache.set({
			mbids: [...mbidSet],
			requested: [...requestedSet],
			monitored: [...monitoredSet]
		});
	}

	async function initialize() {
		const state = get({ subscribe });
		if (state.initialized || state.loading) return;

		const cached = cache.get();
		if (cached) {
			const normalized = normalizeCachedData(cached.data);
			const mbids = normalized.mbids.map((m) => m.toLowerCase());
			const requested = normalized.requested.map((m) => m.toLowerCase());
			const monitored = normalized.monitored.map((m) => m.toLowerCase());

			if (mbids.length === 0 && requested.length === 0 && monitored.length === 0) {
				await fetchLibraryMbids(false);
				return;
			}

			update((s) => ({
				...s,
				mbidSet: new Set(mbids),
				requestedSet: new Set(requested),
				monitoredSet: new Set(monitored),
				lastUpdated: cached.timestamp,
				initialized: true
			}));

			const BACKGROUND_REFRESH_TTL = 30_000;
			if (Date.now() - cached.timestamp > BACKGROUND_REFRESH_TTL) {
				fetchLibraryMbids(true);
			}
		} else {
			await fetchLibraryMbids(false);
		}
	}

	async function fetchLibraryMbids(background = false) {
		if (!background) {
			update((s) => ({ ...s, loading: true }));
		}

		try {
			const data = await api.global.get<{
				mbids?: string[];
				requested_mbids?: string[];
				monitored_mbids?: string[];
			}>('/api/v1/library/mbids');
			const mbids: string[] = (data.mbids || []).map((m: string) => m.toLowerCase());
			const requested: string[] = (data.requested_mbids || []).map((m: string) => m.toLowerCase());
			const monitored: string[] = (data.monitored_mbids || []).map((m: string) => m.toLowerCase());

			update((s) => ({
				...s,
				mbidSet: new Set(mbids),
				requestedSet: new Set(requested),
				monitoredSet: new Set(monitored),
				loading: false,
				lastUpdated: Date.now(),
				initialized: true
			}));

			cache.set({ mbids, requested, monitored });
		} catch {
			if (!background) {
				update((s) => ({ ...s, loading: false, initialized: true }));
			}
		}
	}

	function isInLibrary(mbid: string | null | undefined): boolean {
		if (!mbid) return false;
		const state = get({ subscribe });
		return state.mbidSet.has(mbid.toLowerCase());
	}

	function addMbid(mbid: string) {
		update((s) => {
			const newSet = new Set(s.mbidSet);
			newSet.add(mbid.toLowerCase());
			const newRequested = new Set(s.requestedSet);
			newRequested.delete(mbid.toLowerCase());
			const newMonitored = new Set(s.monitoredSet);
			newMonitored.delete(mbid.toLowerCase());
			persistState(newSet, newRequested, newMonitored);
			return { ...s, mbidSet: newSet, requestedSet: newRequested, monitoredSet: newMonitored };
		});
	}

	function removeMbid(mbid: string) {
		update((s) => {
			const newSet = new Set(s.mbidSet);
			newSet.delete(mbid.toLowerCase());
			const newRequested = new Set(s.requestedSet);
			newRequested.delete(mbid.toLowerCase());
			const newMonitored = new Set(s.monitoredSet);
			newMonitored.delete(mbid.toLowerCase());
			persistState(newSet, newRequested, newMonitored);
			return { ...s, mbidSet: newSet, requestedSet: newRequested, monitoredSet: newMonitored };
		});
	}

	function addRequested(mbid: string) {
		update((s) => {
			if (s.mbidSet.has(mbid.toLowerCase())) {
				return s;
			}
			const lower = mbid.toLowerCase();
			const newRequested = new Set(s.requestedSet);
			newRequested.add(lower);
			const newMonitored = new Set(s.monitoredSet);
			newMonitored.delete(lower);
			persistState(s.mbidSet, newRequested, newMonitored);
			return { ...s, requestedSet: newRequested, monitoredSet: newMonitored };
		});
	}

	function isRequested(mbid: string | null | undefined): boolean {
		if (!mbid) return false;
		const lower = mbid.toLowerCase();
		const state = get({ subscribe });
		return state.requestedSet.has(lower) && !state.mbidSet.has(lower);
	}

	function isMonitored(mbid: string | null | undefined): boolean {
		if (!mbid) return false;
		const state = get({ subscribe });
		return (
			state.monitoredSet.has(mbid.toLowerCase()) &&
			!state.mbidSet.has(mbid.toLowerCase()) &&
			!state.requestedSet.has(mbid.toLowerCase())
		);
	}

	function setMonitored(mbid: string, monitored: boolean) {
		update((s) => {
			const newMonitored = new Set(s.monitoredSet);
			if (monitored) {
				newMonitored.add(mbid.toLowerCase());
			} else {
				newMonitored.delete(mbid.toLowerCase());
			}
			persistState(s.mbidSet, s.requestedSet, newMonitored);
			return { ...s, monitoredSet: newMonitored };
		});
	}

	async function refresh() {
		await fetchLibraryMbids(false);
	}

	async function refreshIfStale(ttlMs: number) {
		const state = get({ subscribe });
		if (!state.initialized) {
			await initialize();
			return;
		}
		if (state.lastUpdated && Date.now() - state.lastUpdated < ttlMs) return;
		await fetchLibraryMbids(true);
	}

	return {
		subscribe,
		initialize,
		refresh,
		refreshIfStale,
		isInLibrary,
		addMbid,
		removeMbid,
		isRequested,
		addRequested,
		isMonitored,
		setMonitored,
		updateCacheTTL: cache.updateTTL
	};
}

export const libraryStore = createLibraryStore();
