import { get, writable } from 'svelte/store';
import { API } from '$lib/constants';

interface IntegrationStatus {
	lidarr: boolean;
	jellyfin: boolean;
	listenbrainz: boolean;
	youtube: boolean;
	loaded: boolean;
}

function createIntegrationStore() {
	const { subscribe, set, update } = writable<IntegrationStatus>({
		lidarr: false,
		jellyfin: false,
		listenbrainz: false,
		youtube: false,
		loaded: false
	});
	let loadPromise: Promise<void> | null = null;

	return {
		subscribe,
		setStatus: (status: Partial<IntegrationStatus>) => {
			update(current => ({ ...current, ...status, loaded: true }));
		},
		setLidarrConfigured: (configured: boolean) => {
			update(current => ({ ...current, lidarr: configured }));
		},
		reset: () => {
			set({ lidarr: false, jellyfin: false, listenbrainz: false, youtube: false, loaded: false });
		},
		ensureLoaded: async () => {
			const current = get({ subscribe });
			if (current.loaded) return;
			if (loadPromise) return loadPromise;

			loadPromise = (async () => {
				try {
					const res = await fetch(API.homeIntegrationStatus());
					if (res.ok) {
						const status = await res.json();
						update((state) => ({ ...state, ...status, loaded: true }));
						return;
					}
				} catch {}

				update((state) => ({ ...state, loaded: true }));
			})().finally(() => {
				loadPromise = null;
			});

			return loadPromise;
		}
	};
}

export const integrationStore = createIntegrationStore();
