import { api } from '$lib/api/client';
import { API, CACHE_TTL } from '$lib/constants';
import type { MusicSource } from '$lib/stores/musicSource';
import type { DiscoverResponse } from '$lib/types';
import type { Getter } from '$lib/utils/typeHelpers';
import { createQuery } from '@tanstack/svelte-query';
import { DiscoverQueryKeyFactory } from './DiscoverQueryKeyFactory';

export const getDiscoverQuery = (getSource: Getter<MusicSource>) =>
	createQuery(() => ({
		staleTime: CACHE_TTL.DISCOVER,
		queryKey: DiscoverQueryKeyFactory.discover(getSource()),
		queryFn: ({ signal }) =>
			api.global.get<DiscoverResponse>(API.discover(getSource()), {
				signal
			})
	}));
