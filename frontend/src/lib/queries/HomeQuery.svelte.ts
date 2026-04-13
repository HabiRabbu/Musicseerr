import { api } from '$lib/api/client';
import { API, CACHE_TTL } from '$lib/constants';
import type { MusicSource } from '$lib/stores/musicSource';
import type { HomeResponse } from '$lib/types';
import type { Getter } from '$lib/utils/typeHelpers';
import { createQuery } from '@tanstack/svelte-query';

const keyFactory = {
	home: (source: MusicSource) => ['home', source] as const
};

export const getHomeQuery = (getSource: Getter<MusicSource>) =>
	createQuery(() => ({
		staleTime: CACHE_TTL.HOME,
		queryKey: keyFactory.home(getSource()),
		queryFn: ({ signal }) =>
			api.global.get<HomeResponse>(API.home(getSource()), {
				signal
			})
	}));
