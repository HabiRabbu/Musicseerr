import { writable } from 'svelte/store';
import type { UserPreferences } from '$lib/types';

const API_BASE = '/api';


const defaultPreferences: UserPreferences = {
	primary_types: ['album', 'ep', 'single'],
	secondary_types: ['studio'],
	release_statuses: ['official']
};


const { subscribe, set, update } = writable<UserPreferences>(defaultPreferences);


async function loadPreferences(): Promise<void> {
	try {
		const response = await fetch(`${API_BASE}/settings/preferences`);
		if (response.ok) {
			const prefs: UserPreferences = await response.json();
			set(prefs);
		}
	} catch (e) {
		console.error('Failed to load preferences:', e);
	}
}


async function savePreferences(prefs: UserPreferences): Promise<boolean> {
	try {
		const response = await fetch(`${API_BASE}/settings/preferences`, {
			method: 'PUT',
			headers: {
				'Content-Type': 'application/json'
			},
			body: JSON.stringify(prefs)
		});

		if (response.ok) {
			const updated: UserPreferences = await response.json();
			set(updated);
			return true;
		}
		return false;
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
