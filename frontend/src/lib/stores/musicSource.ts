import { writable, get } from 'svelte/store';
import { browser } from '$app/environment';
import { CACHE_KEYS, PAGE_SOURCE_KEYS } from '$lib/constants';

export type MusicSource = 'listenbrainz' | 'lastfm';
export type MusicSourcePage = keyof typeof PAGE_SOURCE_KEYS;

interface MusicSourceState {
	source: MusicSource;
	loaded: boolean;
}

function createMusicSourceStore() {
	const { subscribe, set, update } = writable<MusicSourceState>({
		source: 'listenbrainz',
		loaded: false,
	});

	let loadPromise: Promise<void> | null = null;
	let mutationVersion = 0;

	function isMusicSource(value: unknown): value is MusicSource {
		return value === 'listenbrainz' || value === 'lastfm';
	}

	function getPageStorageKey(page: MusicSourcePage): string {
		return PAGE_SOURCE_KEYS[page];
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
					localStorage.removeItem(CACHE_KEYS.HOME_CACHE);
					localStorage.removeItem(CACHE_KEYS.DISCOVER_CACHE);
				}
				const res = await fetch('/api/settings/primary-source');
				if (res.ok) {
					const data = await res.json();
					const fetchedSource = isMusicSource(data.source) ? data.source : 'listenbrainz';
					if (mutationVersion === loadStartedAtVersion) {
						set({ source: fetchedSource, loaded: true });
					} else {
						update((s) => ({ ...s, loaded: true }));
					}
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
			const res = await fetch('/api/settings/primary-source', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ source }),
			});
			if (res.ok) {
				if (mutationVersion === saveVersion) {
					set({ source, loaded: true });
				}
				return true;
			}
			return false;
		} catch {
			return false;
		}
	}

	function setSource(source: MusicSource): void {
		mutationVersion += 1;
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
		getPageSource,
		setPageSource,
	};
}

export const musicSourceStore = createMusicSourceStore();
