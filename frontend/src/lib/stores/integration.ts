import { writable } from 'svelte/store';

interface IntegrationStatus {
	lidarr: boolean;
	jellyfin: boolean;
	listenbrainz: boolean;
	loaded: boolean;
}

function createIntegrationStore() {
	const { subscribe, set, update } = writable<IntegrationStatus>({
		lidarr: false,
		jellyfin: false,
		listenbrainz: false,
		loaded: false
	});

	return {
		subscribe,
		setStatus: (status: Partial<IntegrationStatus>) => {
			update(current => ({ ...current, ...status, loaded: true }));
		},
		setLidarrConfigured: (configured: boolean) => {
			update(current => ({ ...current, lidarr: configured }));
		},
		reset: () => {
			set({ lidarr: false, jellyfin: false, listenbrainz: false, loaded: false });
		}
	};
}

export const integrationStore = createIntegrationStore();
