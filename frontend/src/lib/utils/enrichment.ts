import type {
	Artist,
	Album,
	EnrichmentResponse,
	EnrichmentSource,
	ArtistEnrichmentRequest,
	AlbumEnrichmentRequest
} from '$lib/types';
import { api } from '$lib/api/client';

export function getListenTitle(
	source: EnrichmentSource,
	kind: 'artist' | 'album' = 'artist'
): string {
	if (source === 'lastfm') return kind === 'album' ? 'Last.fm plays' : 'Last.fm listeners';
	if (source === 'listenbrainz') return 'ListenBrainz plays';
	return 'Plays';
}

export async function fetchEnrichmentBatch(
	artists: ArtistEnrichmentRequest[],
	albums: AlbumEnrichmentRequest[],
	signal?: AbortSignal
): Promise<EnrichmentResponse | null> {
	if (artists.length === 0 && albums.length === 0) return null;

	try {
		return await api.post<EnrichmentResponse>(
			'/api/v1/search/enrich/batch',
			{ artists, albums },
			{ signal }
		);
	} catch {
		return null;
	}
}

export function applyArtistEnrichment(artists: Artist[], enrichment: EnrichmentResponse): Artist[] {
	if (enrichment.artists.length === 0) return artists;

	const map = new Map(enrichment.artists.map((a) => [a.musicbrainz_id, a]));
	return artists.map((artist) => {
		const enrich = map.get(artist.musicbrainz_id);
		if (!enrich) return artist;
		return {
			...artist,
			release_group_count: enrich.release_group_count ?? artist.release_group_count,
			listen_count: enrich.listen_count ?? artist.listen_count
		};
	});
}

export function applyAlbumEnrichment(albums: Album[], enrichment: EnrichmentResponse): Album[] {
	if (enrichment.albums.length === 0) return albums;

	const map = new Map(enrichment.albums.map((a) => [a.musicbrainz_id, a]));
	return albums.map((album) => {
		const enrich = map.get(album.musicbrainz_id);
		if (!enrich) return album;
		return {
			...album,
			track_count: enrich.track_count ?? album.track_count,
			listen_count: enrich.listen_count ?? album.listen_count
		};
	});
}
