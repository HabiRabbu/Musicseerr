import { api } from '$lib/api/client';
import { API } from '$lib/constants';
import { DEFAULT_SOURCE, isMusicSource } from '$lib/stores/musicSource';
import type { LayoutLoad } from './$types';

export const ssr = false;
export const prerender = false;

export const load: LayoutLoad = async () => {
	try {
		const data = await api.global.get<{ source: unknown }>(API.settingsPrimarySource());
		const primarySource = isMusicSource(data.source) ? data.source : DEFAULT_SOURCE;

		return {
			primarySource
		};
	} catch {
		return {
			primarySource: DEFAULT_SOURCE
		};
	}
};
