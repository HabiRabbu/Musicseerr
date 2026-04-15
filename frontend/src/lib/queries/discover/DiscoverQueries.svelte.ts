import { api } from '$lib/api/client';
import { API, CACHE_TTL } from '$lib/constants';
import type { MusicSource } from '$lib/stores/musicSource';
import type { DiscoverResponse } from '$lib/types';
import { createQuery } from '@tanstack/svelte-query';
import { DiscoverQueryKeyFactory } from './DiscoverQueryKeyFactory';
import type { Getter } from 'runed';

const MAX_RETRY_TIME = 5 * 60 * 1000; // 5 minutes

export const getDiscoverQuery = (getSource: Getter<MusicSource>) => {
	let shouldRefetchStart = $state<false | Date>(false);

	const query = createQuery(() => ({
		staleTime: CACHE_TTL.DISCOVER,
		queryKey: DiscoverQueryKeyFactory.discover(getSource()),
		refetchInterval: () => {
			const now = Date.now();
			if (shouldRefetchStart && now - (shouldRefetchStart as Date).getTime() < MAX_RETRY_TIME) {
				return 3_000; // Refetch every 3 seconds if data is empty
			}
			return undefined;
		},
		queryFn: ({ signal }) =>
			api.global.get<DiscoverResponse>(API.discover(getSource()), {
				signal
			})
	}));

	const dataHasContent = $derived(
		(query.data?.because_you_listen_to?.length ?? 0) > 0 ||
			query.data?.fresh_releases != null ||
			query.data?.missing_essentials != null ||
			query.data?.globally_trending != null
	);

	$effect(() => {
		if (!query.isLoading && !query.isFetching && !dataHasContent) {
			// eslint-disable-next-line svelte/prefer-svelte-reactivity
			shouldRefetchStart = new Date();
		} else {
			shouldRefetchStart = false;
		}
	});

	return query;
};
