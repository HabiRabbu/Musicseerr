import { CACHE_TTL } from '$lib/constants';
import { fetchPlaylists } from '$lib/api/playlists';
import { createQuery } from '@tanstack/svelte-query';
import type { Getter } from 'runed';
import { PlaylistQueryKeyFactory } from './PlaylistQueryKeyFactory';

export const getPlaylistListQuery = (getEnabled: Getter<boolean>) =>
	createQuery(() => ({
		staleTime: CACHE_TTL.DEFAULT,
		queryKey: PlaylistQueryKeyFactory.list(),
		queryFn: () => fetchPlaylists(),
		enabled: getEnabled()
	}));
