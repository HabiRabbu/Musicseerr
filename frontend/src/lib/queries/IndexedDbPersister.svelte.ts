import type {
	AsyncStorage,
	PersistedClient,
	PersistedQuery,
	Persister
} from '@tanstack/svelte-query-persist-client';
import { del, entries, get, set } from 'idb-keyval';

export function createIDBPersister(idbValidKey: string = 'tanstackQuery') {
	return {
		persistClient: async (client: PersistedClient) => {
			await set(idbValidKey, client);
		},
		restoreClient: async () => {
			return await get<PersistedClient>(idbValidKey);
		},
		removeClient: async () => {
			await del(idbValidKey);
		}
	} satisfies Persister;
}

export function createIDBStorage(): AsyncStorage<PersistedQuery> {
	return {
		getItem: async (key: string) => {
			const val = await get<PersistedQuery>(key);
			return val;
		},
		setItem: async (key: string, value: PersistedQuery) => {
			// Snapshot Svelte state proxies before storing them in IndexedDB.
			await set(key, $state.snapshot(value));
		},
		removeItem: async (key: string) => {
			await del(key);
		},
		entries: async () => {
			return await entries();
		}
	};
}
