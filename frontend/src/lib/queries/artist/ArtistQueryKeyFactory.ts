import type { MusicSource } from '$lib/stores/musicSource';

export const ArtistQueryKeyFactory = {
	basic: (id: string) => ['artist', id] as const,
	extended: (id: string) => ['artist', id, 'extended'] as const,
	similarArtists: (id: string, source: MusicSource) => ['similar-artists', id, { source }] as const,
	topAlbums: (id: string, source: MusicSource) => ['artist', id, 'top-albums', { source }] as const,
	topSongs: (id: string, source: MusicSource) => ['artist', id, 'top-songs', { source }] as const,
	lastFmEnrichment: (id: string, artistName?: string) =>
		['artist', id, 'lastfm-enrichment', { artistName }] as const,
	releases: (id: string) => ['artist', id, 'releases'] as const
};
