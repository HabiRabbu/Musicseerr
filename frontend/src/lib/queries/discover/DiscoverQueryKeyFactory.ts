import type { MusicSource } from '$lib/stores/musicSource';

export const DiscoverQueryKeyFactory = {
	discover: (source: MusicSource) => ['discover', source] as const
};
