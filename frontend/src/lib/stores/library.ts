import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';

interface LibraryState {
  mbidSet: Set<string>;
  loading: boolean;
  lastUpdated: number | null;
  initialized: boolean;
}

const CACHE_KEY = 'musicseerr_library_mbids';
const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

const initialState: LibraryState = {
  mbidSet: new Set(),
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
      return { ...s, mbidSet: newSet };
    });
  }
  
  async function refresh() {
    await fetchLibraryMbids(false);
  }

  return {
    subscribe,
    initialize,
    refresh,
    isInLibrary,
    addMbid
  };
}

export const libraryStore = createLibraryStore();
