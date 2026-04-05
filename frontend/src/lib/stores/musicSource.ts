import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { PAGE_SOURCE_KEYS } from '$lib/constants';
import { api } from '$lib/api/client';

export type MusicSource = 'listenbrainz' | 'lastfm';
export type MusicSourcePage = keyof typeof PAGE_SOURCE_KEYS;

const CACHED_SOURCE_KEY = 'musicseerr_primary_source';
const DEFAULT_SOURCE: MusicSource = 'listenbrainz';

interface MusicSourceState {
	source: MusicSource;
	loaded: boolean;
}

function isMusicSource(value: unknown): value is MusicSource {
	return value === 'listenbrainz' || value === 'lastfm';
}

function readCachedSource(): MusicSource {
	if (!browser) return DEFAULT_SOURCE;
	const stored = localStorage.getItem(CACHED_SOURCE_KEY);
	return isMusicSource(stored) ? stored : DEFAULT_SOURCE;
}

function createMusicSourceStore() {
	const { subscribe, set, update } = writable<MusicSourceState>({
		source: readCachedSource(),
		loaded: false
	});

	let loadPromise: Promise<void> | null = null;
	let mutationVersion = 0;

	function getPageStorageKey(page: MusicSourcePage): string {
		return PAGE_SOURCE_KEYS[page];
	}

	function persistSource(source: MusicSource): void {
		if (browser) {
			localStorage.setItem(CACHED_SOURCE_KEY, source);
		}
	}

	function getCachedSource(): MusicSource {
		return readCachedSource();
	}

	async function load(): Promise<void> {
		const current = get({ subscribe });
		if (current.loaded) return;
		if (loadPromise) return loadPromise;
		const loadStartedAtVersion = mutationVersion;

		loadPromise = (async () => {
			try {
				if (browser) {
					localStorage.removeItem('home_source');
					localStorage.removeItem('discover_source');
					localStorage.removeItem('artist-discovery_source');
				}
				const data = await api.global.get<{ source: unknown }>('/api/v1/settings/primary-source');
				const fetchedSource = isMusicSource(data.source) ? data.source : DEFAULT_SOURCE;
				if (mutationVersion === loadStartedAtVersion) {
					persistSource(fetchedSource);
					set({ source: fetchedSource, loaded: true });
				} else {
					update((s) => ({ ...s, loaded: true }));
				}
			} catch {
				update((s) => ({ ...s, loaded: true }));
			} finally {
				loadPromise = null;
			}
		})();

		return loadPromise;
	}

	async function save(source: MusicSource): Promise<boolean> {
		const saveVersion = ++mutationVersion;
		try {
			await api.global.put('/api/v1/settings/primary-source', { source });
			persistSource(source);
			if (mutationVersion === saveVersion) {
				set({ source, loaded: true });
			}
			return true;
		} catch {
			return false;
		}
	}

	function setSource(source: MusicSource): void {
		mutationVersion += 1;
		persistSource(source);
		set({ source, loaded: true });
	}

	function getSource(): MusicSource {
		return get({ subscribe }).source;
	}

	function getPageSource(page: MusicSourcePage): MusicSource {
		const fallbackSource = getSource();
		if (!browser) return fallbackSource;
		const storedSource = localStorage.getItem(getPageStorageKey(page));
		return isMusicSource(storedSource) ? storedSource : fallbackSource;
	}

	function setPageSource(page: MusicSourcePage, source: MusicSource): void {
		if (!browser) return;
		localStorage.setItem(getPageStorageKey(page), source);
	}

	return {
		subscribe,
		load,
		save,
		setSource,
		getSource,
		getCachedSource,
		getPageSource,
		setPageSource
	};
}

export const musicSourceStore = createMusicSourceStore();
