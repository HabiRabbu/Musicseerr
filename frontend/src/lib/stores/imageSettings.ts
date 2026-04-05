import { writable } from 'svelte/store';
import { api } from '$lib/api/client';

interface ImageSettings {
	directRemoteImagesEnabled: boolean;
}

const defaultSettings: ImageSettings = {
	directRemoteImagesEnabled: true
};

const { subscribe, set } = writable<ImageSettings>(defaultSettings);

let lastFetch = 0;
const CACHE_MS = 60_000;

async function load(): Promise<void> {
	const now = Date.now();
	if (now - lastFetch < CACHE_MS) return;

	try {
		const data = await api.global.get<{ direct_remote_images_enabled?: boolean }>(
			'/api/v1/settings/advanced'
		);
		set({
			directRemoteImagesEnabled: data.direct_remote_images_enabled ?? true
		});
		lastFetch = now;
	} catch (e) {
		console.warn('Failed to load image settings:', e);
	}
}

export const imageSettingsStore = {
	subscribe,
	load
};
