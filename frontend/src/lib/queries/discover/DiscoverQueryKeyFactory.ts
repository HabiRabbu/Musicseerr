import type { MusicSource } from '$lib/stores/musicSource';

export const DiscoverQueryKeyFactory = {
	prefix: ['discover'] as const,
	discover: (source: MusicSource) => [...DiscoverQueryKeyFactory.prefix, source] as const,
	radio: (seedType: string, seedId: string, source: MusicSource) =>
		[...DiscoverQueryKeyFactory.prefix, 'radio', seedType, seedId, { source }] as const,
	playlistSuggestions: (playlistId: string, source?: MusicSource | null) =>
		[...DiscoverQueryKeyFactory.prefix, 'playlist-suggestions', playlistId, source ?? null] as const
};
