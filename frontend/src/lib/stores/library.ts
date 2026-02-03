import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';

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

	function loadFromStorage(): { mbids: string[]; timestamp: number } | null {
		if (!browser) return null;

		try {
			const cached = localStorage.getItem(CACHE_KEYS.LIBRARY_MBIDS);
			if (cached) {
				return JSON.parse(cached);
			}
		} catch (e) {
			console.error('Failed to load library from storage:', e);
		}
		return null;
	}

	function saveToStorage(mbids: string[]) {
		if (!browser) return;

		try {
			localStorage.setItem(
				CACHE_KEYS.LIBRARY_MBIDS,
				JSON.stringify({
					mbids,
					timestamp: Date.now()
				})
			);
		} catch (e) {
			console.error('Failed to save library to storage:', e);
		}
	}

	async function initialize() {
		const state = get({ subscribe });
		if (state.initialized || state.loading) return;

		const cached = loadFromStorage();
		if (cached && cached.mbids.length > 0) {
			update((s) => ({
				...s,
				mbidSet: new Set(cached.mbids),
				lastUpdated: cached.timestamp,
				initialized: true
			}));

			if (Date.now() - cached.timestamp > CACHE_TTL.LIBRARY) {
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

			saveToStorage(mbids);
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
		addRequested
	};
}

export const libraryStore = createLibraryStore();
