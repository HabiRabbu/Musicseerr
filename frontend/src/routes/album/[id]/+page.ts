import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params, fetch }) => {
	try {
		const res = await fetch(`/api/album/${params.id}`);
		if (res.ok) {
			const album = await res.json();
			return {
				albumId: params.id,
				album
			};
		}
		return {
			albumId: params.id,
			album: null,
			error: 'Failed to load album'
		};
	} catch (e) {
		return {
			albumId: params.id,
			album: null,
			error: 'Error loading album'
		};
	}
};
