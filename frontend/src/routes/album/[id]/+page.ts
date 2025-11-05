import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	// Return immediately with just the album ID
	// The component will fetch the data in the background
	return {
		albumId: params.id,
		album: null
	};
};
