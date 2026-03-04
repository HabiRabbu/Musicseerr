import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	return {
		playlistId: params.id
	};
};
