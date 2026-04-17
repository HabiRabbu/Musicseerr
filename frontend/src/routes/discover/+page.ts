import { getDiscoverQueryOptions } from '$lib/queries/discover/DiscoverQuery.svelte';
import { queryClient } from '$lib/queries/QueryClient';
import { musicSourceStore } from '$lib/stores/musicSource';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	const source = musicSourceStore.getCachedSource();
	await queryClient.prefetchQuery(getDiscoverQueryOptions(source));

	return {};
};
