import type { Artist, Album, EnrichmentResponse } from '$lib/types';

export async function fetchEnrichmentBatch(
	artistMbids: string[],
	albumMbids: string[],
	signal?: AbortSignal
): Promise<EnrichmentResponse | null> {
	if (artistMbids.length === 0 && albumMbids.length === 0) return null;

	const params = new URLSearchParams();
	if (artistMbids.length > 0) params.set('artist_mbids', artistMbids.join(','));
	if (albumMbids.length > 0) params.set('album_mbids', albumMbids.join(','));

	const res = await fetch(`/api/search/enrich/batch?${params.toString()}`, { signal });
	if (!res.ok) return null;

	return res.json();
}

export function applyArtistEnrichment(
	artists: Artist[],
	enrichment: EnrichmentResponse
): Artist[] {
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
