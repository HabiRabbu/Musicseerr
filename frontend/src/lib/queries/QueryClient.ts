import { browser } from '$app/environment';
import {
	type InferDataFromTag,
	QueryClient,
	type QueryFilters,
	type QueryKey,
	type SetDataOptions,
	type Updater
} from '@tanstack/svelte-query';
import { experimental_createQueryPersister } from '@tanstack/svelte-query-persist-client';
import { createIDBStorage } from './IndexedDbPersister.svelte';

/**
 * Maximum age for queries to be persisted.
 * @see https://tanstack.com/query/latest/docs/framework/react/plugins/persistQueryClient#how-it-works
 */
export const QUERY_MAX_AGE = 1000 * 60 * 60 * 24 * 7; // 7 days

export const queryPersister = experimental_createQueryPersister({
	storage: createIDBStorage(),
	maxAge: QUERY_MAX_AGE,
	// No need to serialize/deserialize since we're using IndexedDB which can store complex objects.
	serialize: (persistedQuery) => persistedQuery,
	deserialize: (cached) => cached
});

export const setQueriesDataWithPersister = async <TQueryFnData>(
	filters: QueryFilters,
	updater: Updater<NoInfer<TQueryFnData> | undefined, NoInfer<TQueryFnData> | undefined>
) => {
	// eslint-disable-next-line no-restricted-syntax
	const setQueriesDataReturn = queryClient.setQueriesData<TQueryFnData>(filters, updater);
	for (const modifiedQuery of setQueriesDataReturn) {
		await queryPersister.persistQueryByKey(modifiedQuery[0], queryClient);
	}
};
export const setQueryDataWithPersister = async <
	TQueryFnData = unknown,
	TTaggedQueryKey extends QueryKey = QueryKey,
	TInferredQueryFnData = InferDataFromTag<TQueryFnData, TTaggedQueryKey>
>(
	queryKey: TTaggedQueryKey,
	updater: Updater<
		NoInfer<TInferredQueryFnData> | undefined,
		NoInfer<TInferredQueryFnData> | undefined
	>,
	options?: SetDataOptions
) => {
	// eslint-disable-next-line no-restricted-syntax
	await queryClient.setQueryData<TQueryFnData, TTaggedQueryKey, TInferredQueryFnData>(
		queryKey,
		updater,
		options
	);
	await queryPersister.persistQueryByKey(queryKey, queryClient);
};

/**
 * Global query client, used to manage all queries in the application.
 */
export const queryClient = new QueryClient({
	defaultOptions: {
		queries: {
			enabled: browser,
			retry: false,
			refetchOnWindowFocus: true,
			staleTime: 1000 * 60 * 1, // 1 minute,
			gcTime: 1000 * 30, // 30 seconds
			persister: queryPersister.persisterFn
		}
	}
});
