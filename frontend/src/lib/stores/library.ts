import { writable, get } from 'svelte/store';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';

export interface LibraryState {
	mbidSet: Set<string>;
	requestedSet: Set<string>;
	loading: boolean;
	lastUpdated: number | null;
	initialized: boolean;
}

const initialState: LibraryState = {
	mbidSet: new Set(),
	requestedSet: new Set(),
	loading: false,
	lastUpdated: null,
	initialized: false
};

function createLibraryStore() {
	const { subscribe, set, update } = writable<LibraryState>(initialState);
	const cache = createLocalStorageCache<string[]>(CACHE_KEYS.LIBRARY_MBIDS, CACHE_TTL.LIBRARY);

	async function initialize() {
		const state = get({ subscribe });
		if (state.initialized || state.loading) return;

		const cached = cache.get();
		if (cached && cached.data.length > 0) {
			update((s) => ({
				...s,
				mbidSet: new Set(cached.data),
				lastUpdated: cached.timestamp,
				initialized: true
			}));

			if (cache.isStale(cached.timestamp)) {
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
			const res = await fetch('/api/library/mbids');
			if (!res.ok) throw new Error('Failed to fetch library');

			const data = await res.json();
			const mbids: string[] = (data.mbids || []).map((m: string) => m.toLowerCase());

			update((s) => ({
				...s,
				mbidSet: new Set(mbids),
				loading: false,
				lastUpdated: Date.now(),
				initialized: true
			}));

			cache.set(mbids);
		} catch (e) {
			console.error('Failed to fetch library MBIDs:', e);
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
			return { ...s, mbidSet: newSet, requestedSet: newRequested };
		});
	}

	function addRequested(mbid: string) {
		update((s) => {
			if (s.mbidSet.has(mbid.toLowerCase())) {
				return s;
			}
			const newSet = new Set(s.requestedSet);
			newSet.add(mbid.toLowerCase());
			return { ...s, requestedSet: newSet };
		});
	}

	function isRequested(mbid: string | null | undefined): boolean {
		if (!mbid) return false;
		const state = get({ subscribe });
		return state.requestedSet.has(mbid.toLowerCase()) && !state.mbidSet.has(mbid.toLowerCase());
	}

	async function refresh() {
		await fetchLibraryMbids(false);
	}

	return {
		subscribe,
		initialize,
		refresh,
		isInLibrary,
		addMbid,
		isRequested,
		addRequested,
		updateCacheTTL: cache.updateTTL
	};
}

export const libraryStore = createLibraryStore();
