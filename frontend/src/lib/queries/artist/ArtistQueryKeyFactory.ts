import type { MusicSource } from '$lib/stores/musicSource';

export const ArtistQueryKeyFactory = {
	prefix: ['artist'] as const,
	basic: (id: string) => [...ArtistQueryKeyFactory.prefix, id] as const,
	extended: (id: string) => [...ArtistQueryKeyFactory.prefix, id, 'extended'] as const,
	topAlbums: (id: string, source: MusicSource) =>
		[...ArtistQueryKeyFactory.prefix, id, 'top-albums', { source }] as const,
	topSongs: (id: string, source: MusicSource) =>
		[...ArtistQueryKeyFactory.prefix, id, 'top-songs', { source }] as const,
	lastFmEnrichment: (id: string, artistName?: string) =>
		[...ArtistQueryKeyFactory.prefix, id, 'lastfm-enrichment', { artistName }] as const,
	releases: (id: string) => [...ArtistQueryKeyFactory.prefix, id, 'releases'] as const,
	similarArtists: (id: string, source: MusicSource) => ['similar-artists', id, { source }] as const
};
