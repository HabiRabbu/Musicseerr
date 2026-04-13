import { getBasicArtistQueryOptions } from '$lib/queries/artist/ArtistQueries.svelte';
import { queryClient } from '$lib/queries/QueryClient';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	queryClient.prefetchQuery(getBasicArtistQueryOptions(params.id));

	return {
		artistId: params.id
	};
};
