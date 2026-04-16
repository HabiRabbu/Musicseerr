import type { MusicSource } from '$lib/stores/musicSource';

export const DiscoverQueryKeyFactory = {
	prefix: ['discover'] as const,
	discover: (source: MusicSource) => [...DiscoverQueryKeyFactory.prefix, source] as const
};
