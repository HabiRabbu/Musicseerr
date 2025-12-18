import { writable, get } from 'svelte/store';
import type { Artist, Album } from '$lib/types';

interface SearchCache {
	query: string;
	artists: Artist[];
	albums: Album[];
	timestamp: number;
}

const CACHE_TTL = 5 * 60 * 1000; // 5 minutes

function createSearchStore() {
	const { subscribe, set, update } = writable<SearchCache | null>(null);

	return {
		subscribe,
		setResults(query: string, artists: Artist[], albums: Album[]) {
			set({
				query,
				artists,
				albums,
				timestamp: Date.now()
			});
		},
		updateArtists(artists: Artist[]) {
			update((cache) => {
				if (cache) {
					return { ...cache, artists };
				}
				return cache;
			});
		},
		updateAlbums(albums: Album[]) {
			update((cache) => {
				if (cache) {
					return { ...cache, albums };
				}
				return cache;
			});
		},
		getCache(query: string): SearchCache | null {
			const cache = get({ subscribe });
			if (cache && cache.query === query && Date.now() - cache.timestamp < CACHE_TTL) {
				return cache;
			}
			return null;
		},
		clear() {
			set(null);
		}
	};
}

export const searchStore = createSearchStore();
