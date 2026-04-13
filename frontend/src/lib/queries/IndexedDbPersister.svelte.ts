import type {
	AsyncStorage,
	PersistedClient,
	PersistedQuery,
	Persister
} from '@tanstack/svelte-query-persist-client';
import { del, entries, get, set } from 'idb-keyval';

/**
 * Creates an Indexed DB persister
 * @see https://developer.mozilla.org/en-US/docs/Web/API/IndexedDB_API
 * @see https://tanstack.com/query/latest/docs/framework/react/plugins/persistQueryClient#building-a-persister
 */
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
			// In some cases, a svelte state proxy value appears in the query state, which cannot be stored in IndexedDB.
			// To work around this, we can snapshot the value before storing it.
			console.debug('Setting item in IndexedDB', key, value);
			try {
				await set(key, $state.snapshot(value));
			} catch (e) {
				console.error('Failed to set item in IndexedDB', key, value, e);
				throw e;
			}
		},
		removeItem: async (key: string) => {
			await del(key);
		},
		entries: async () => {
			return await entries();
		}
	};
}
