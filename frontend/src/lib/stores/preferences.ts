import { writable } from 'svelte/store';
import type { UserPreferences } from '$lib/types';
import { api } from '$lib/api/client';

const API_BASE = '/api/v1';

const defaultPreferences: UserPreferences = {
	primary_types: ['album', 'ep', 'single'],
	secondary_types: ['studio'],
	release_statuses: ['official']
};

const { subscribe, set, update } = writable<UserPreferences>(defaultPreferences);

async function loadPreferences(): Promise<void> {
	try {
		const prefs = await api.global.get<UserPreferences>(`${API_BASE}/settings/preferences`);
		set(prefs);
	} catch (e) {
		console.error('Failed to load preferences:', e);
	}
}

async function savePreferences(prefs: UserPreferences): Promise<boolean> {
	try {
		const updated = await api.global.put<UserPreferences>(
			`${API_BASE}/settings/preferences`,
			prefs
		);
		set(updated);
		return true;
	} catch (e) {
		console.error('Failed to save preferences:', e);
		return false;
	}
}

export const preferencesStore = {
	subscribe,
	load: loadPreferences,
	save: savePreferences,
	update
};
