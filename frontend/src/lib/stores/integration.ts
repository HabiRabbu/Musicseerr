import { get, writable } from 'svelte/store';
import { API } from '$lib/constants';
import { api } from '$lib/api/client';

interface IntegrationStatus {
	lidarr: boolean;
	jellyfin: boolean;
	navidrome: boolean;
	listenbrainz: boolean;
	youtube: boolean;
	youtube_api: boolean;
	localfiles: boolean;
	lastfm: boolean;
	loaded: boolean;
}

function createIntegrationStore() {
	const { subscribe, set, update } = writable<IntegrationStatus>({
		lidarr: false,
		jellyfin: false,
		navidrome: false,
		listenbrainz: false,
		youtube: false,
		youtube_api: false,
		localfiles: false,
		lastfm: false,
		loaded: false
	});
	let loadPromise: Promise<void> | null = null;

	return {
		subscribe,
		setStatus: (status: Partial<IntegrationStatus>) => {
			update((current) => ({ ...current, ...status, loaded: true }));
		},
		setLidarrConfigured: (configured: boolean) => {
			update((current) => ({ ...current, lidarr: configured }));
		},
		reset: () => {
			set({
				lidarr: false,
				jellyfin: false,
				navidrome: false,
				listenbrainz: false,
				youtube: false,
				youtube_api: false,
				localfiles: false,
				lastfm: false,
				loaded: false
			});
		},
		ensureLoaded: async () => {
			const current = get({ subscribe });
			if (current.loaded) return;
			if (loadPromise) return loadPromise;

			loadPromise = (async () => {
				try {
					const status = await api.global.get<Partial<IntegrationStatus>>(
						API.homeIntegrationStatus()
					);
					update((state) => ({ ...state, ...status, loaded: true }));
					return;
				} catch {
					// Ignore error
				}

				update((state) => ({ ...state, loaded: true }));
			})().finally(() => {
				loadPromise = null;
			});

			return loadPromise;
		}
	};
}

export const integrationStore = createIntegrationStore();
