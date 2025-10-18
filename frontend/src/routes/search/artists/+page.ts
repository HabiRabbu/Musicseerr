import type { PageLoad } from './$types';

export const load: PageLoad = ({ url }) => {
	const query = url.searchParams.get('q') || '';
	return {
		query
	};
};
