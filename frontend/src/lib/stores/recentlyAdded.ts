import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';

interface LibraryArtist {
	name: string;
	mbid: string;
	album_count: number;
	date_added: string | null;
}

interface LibraryAlbum {
	album: string;
	artist: string;
	artist_mbid: string | null;
	foreignAlbumId: string | null;
	year: number | null;
	monitored: boolean;
	cover_url: string | null;
	date_added: number | null;
}

interface RecentlyAddedData {
	artists: LibraryArtist[];
	albums: LibraryAlbum[];
}

interface RecentlyAddedState {
	data: RecentlyAddedData | null;
	loading: boolean;
	lastUpdated: number | null;
	initialized: boolean;
}

function loadCachedData(): { data: RecentlyAddedData; timestamp: number } | null {
	if (!browser) return null;
	try {
		const cached = localStorage.getItem(CACHE_KEYS.RECENTLY_ADDED);
		if (cached) return JSON.parse(cached);
	} catch {
		// Ignore parse errors
	}
	return null;
}

function getInitialState(): RecentlyAddedState {
	const cached = loadCachedData();
	if (cached?.data) {
		return {
			data: cached.data,
			loading: false,
			lastUpdated: cached.timestamp,
			initialized: true
		};
	}
	return {
		data: null,
		loading: false,
		lastUpdated: null,
		initialized: false
	};
}

function createRecentlyAddedStore() {
	const { subscribe, set, update } = writable<RecentlyAddedState>(getInitialState());

	function saveToStorage(data: RecentlyAddedData) {
		if (!browser) return;

		try {
			localStorage.setItem(
				CACHE_KEYS.RECENTLY_ADDED,
				JSON.stringify({
					data,
					timestamp: Date.now()
				})
			);
		} catch (e) {
		}
	}

	async function initialize() {
		const state = get({ subscribe });
		if (state.loading) return;

		if (state.initialized && state.data) {
			if (state.lastUpdated && Date.now() - state.lastUpdated > CACHE_TTL.RECENTLY_ADDED) {
				fetchRecentlyAdded(true);
			}
			return;
		}

		await fetchRecentlyAdded(false);
	}

	async function fetchRecentlyAdded(background = false) {
		if (!background) {
			update((s) => ({ ...s, loading: true }));
		}

		try {
			const res = await fetch('/api/library/recently-added');
			if (!res.ok) throw new Error('Failed to fetch recently added');

			const data: RecentlyAddedData = await res.json();

			update((s) => ({
				...s,
				data,
				loading: false,
				lastUpdated: Date.now(),
				initialized: true
			}));

			saveToStorage(data);
		} catch (e) {
			if (!background) {
				update((s) => ({ ...s, loading: false, initialized: true }));
			}
		}
	}

	function isStale(): boolean {
		const state = get({ subscribe });
		if (!state.lastUpdated) return true;
		return Date.now() - state.lastUpdated > CACHE_TTL.RECENTLY_ADDED;
	}

	async function refresh() {
		await fetchRecentlyAdded(false);
	}

	async function refreshInBackground() {
		await fetchRecentlyAdded(true);
	}

	return {
		subscribe,
		initialize,
		refresh,
		refreshInBackground,
		isStale
	};
}

export const recentlyAddedStore = createRecentlyAddedStore();

export type { LibraryArtist, LibraryAlbum, RecentlyAddedData, RecentlyAddedState };
