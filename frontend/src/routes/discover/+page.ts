import { getDiscoverQueryOptions } from '$lib/queries/discover/DiscoverQuery.svelte';
import { queryClient } from '$lib/queries/QueryClient';
import type { PageLoad } from './$types';

export const load: PageLoad = async () => {
	queryClient.prefetchQuery(getDiscoverQueryOptions('listenbrainz'));

	return {};
};
