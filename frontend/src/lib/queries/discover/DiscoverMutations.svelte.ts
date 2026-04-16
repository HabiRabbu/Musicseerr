import { api } from '$lib/api/client';
import { API } from '$lib/constants';
import { createMutation } from '@tanstack/svelte-query';
import { invalidateQueriesWithPersister } from '../QueryClient';
import { DiscoverQueryKeyFactory } from './DiscoverQueryKeyFactory';

export const createDiscoverRefreshMutation = () =>
	createMutation(() => ({
		mutationFn: () => api.global.post(API.discoverRefresh()),
		onSuccess: () => {
			invalidateQueriesWithPersister({
				queryKey: DiscoverQueryKeyFactory.prefix
			});
		}
	}));
