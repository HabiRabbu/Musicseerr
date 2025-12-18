import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

interface LibraryState {
  mbidSet: Set<string>;
  requestedSet: Set<string>;
  loading: boolean;
  lastUpdated: number | null;
  initialized: boolean;
}

const CACHE_KEY = 'musicseerr_library_mbids';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

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
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        return JSON.parse(cached);
      }
    } catch (e) {
      // Ignore storage errors
    }
    return null;
  }
  
  function saveToStorage(mbids: string[]) {
    if (!browser) return;
    
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        mbids,
        timestamp: Date.now()
      }));
    } catch (e) {
      // Ignore storage errors
    }
  }
  
  async function initialize() {
    const state = get({ subscribe });
    if (state.initialized || state.loading) return;
    
    const cached = loadFromStorage();
    if (cached && cached.mbids.length > 0) {
      update(s => ({
        ...s,
        mbidSet: new Set(cached.mbids),
        lastUpdated: cached.timestamp,
        initialized: true
      }));
      
      // Background refresh if stale
      if (Date.now() - cached.timestamp > CACHE_TTL) {
        fetchLibraryMbids(true);
      }
    } else {
      await fetchLibraryMbids(false);
    }
  }
  
  async function fetchLibraryMbids(background = false) {
    if (!background) {
      update(s => ({ ...s, loading: true }));
    }
    
    try {
      const res = await fetch('/api/library/mbids');
      if (!res.ok) throw new Error('Failed to fetch library');
      
      const data = await res.json();
      const mbids: string[] = (data.mbids || []).map((m: string) => m.toLowerCase());
      
      update(s => ({
        ...s,
        mbidSet: new Set(mbids),
        loading: false,
        lastUpdated: Date.now(),
        initialized: true
      }));
      
      saveToStorage(mbids);
    } catch (e) {
      if (!background) {
        update(s => ({ ...s, loading: false, initialized: true }));
      }
    }
  }
  
  function isInLibrary(mbid: string | null | undefined): boolean {
    if (!mbid) return false;
    const state = get({ subscribe });
    return state.mbidSet.has(mbid.toLowerCase());
  }
  
  function addMbid(mbid: string) {
    update(s => {
      const newSet = new Set(s.mbidSet);
      newSet.add(mbid.toLowerCase());
      // Remove from requested if it was there
      const newRequested = new Set(s.requestedSet);
      newRequested.delete(mbid.toLowerCase());
      return { ...s, mbidSet: newSet, requestedSet: newRequested };
    });
  }

  function addRequested(mbid: string) {
    update(s => {
      // Don't add to requested if already in library
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
    // Only return true if requested AND not in library
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

// Recently Added Store for library page carousel
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

const RECENTLY_ADDED_CACHE_KEY = 'musicseerr_recently_added';
const RECENTLY_ADDED_TTL = 5 * 60 * 1000; // 5 minutes

function createRecentlyAddedStore() {
	const { subscribe, set, update } = writable<RecentlyAddedState>({
		data: null,
		loading: false,
		lastUpdated: null,
		initialized: false
	});

	function loadFromStorage(): { data: RecentlyAddedData; timestamp: number } | null {
		if (!browser) return null;

		try {
			const cached = localStorage.getItem(RECENTLY_ADDED_CACHE_KEY);
			if (cached) {
				return JSON.parse(cached);
			}
		} catch (e) {
			// Ignore storage errors
		}
		return null;
	}

	function saveToStorage(data: RecentlyAddedData) {
		if (!browser) return;

		try {
			localStorage.setItem(
				RECENTLY_ADDED_CACHE_KEY,
				JSON.stringify({
					data,
					timestamp: Date.now()
				})
			);
		} catch (e) {
			// Ignore storage errors
		}
	}

	async function initialize() {
		const state = get({ subscribe });
		if (state.initialized || state.loading) return;

		const cached = loadFromStorage();
		if (cached && cached.data) {
			update((s) => ({
				...s,
				data: cached.data,
				lastUpdated: cached.timestamp,
				initialized: true
			}));

			// Background refresh if stale
			if (Date.now() - cached.timestamp > RECENTLY_ADDED_TTL) {
				fetchRecentlyAdded(true);
			}
		} else {
			await fetchRecentlyAdded(false);
		}
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
		return Date.now() - state.lastUpdated > RECENTLY_ADDED_TTL;
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
