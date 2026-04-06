import type {
	SimilarArtistsResponse,
	TopSongsResponse,
	TopAlbumsResponse,
	SimilarAlbumsResponse,
	MoreByArtistResponse
} from '$lib/types';

interface ArtistDiscoveryCache {
	similarArtists: SimilarArtistsResponse | null;
	topSongs: TopSongsResponse | null;
	topAlbums: TopAlbumsResponse | null;
	timestamp: number;
}

interface AlbumDiscoveryCache {
	similarAlbums: SimilarAlbumsResponse | null;
	moreByArtist: MoreByArtistResponse | null;
	timestamp: number;
}

let CACHE_TTL_MS = 5 * 60 * 1000;

const artistCache = new Map<string, ArtistDiscoveryCache>();
const albumCache = new Map<string, AlbumDiscoveryCache>();

export function updateDiscoveryCacheTTL(ttlMs: number): void {
	CACHE_TTL_MS = ttlMs;
}

export function getArtistDiscoveryCache(artistId: string): ArtistDiscoveryCache | null {
	const cached = artistCache.get(artistId);
	if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
		return cached;
	}
	return null;
}

export function setArtistDiscoveryCache(
	artistId: string,
	data: Omit<ArtistDiscoveryCache, 'timestamp'>
) {
	artistCache.set(artistId, { ...data, timestamp: Date.now() });
}

export function getAlbumDiscoveryCache(albumId: string): AlbumDiscoveryCache | null {
	const cached = albumCache.get(albumId);
	if (cached && Date.now() - cached.timestamp < CACHE_TTL_MS) {
		return cached;
	}
	return null;
}

export function setAlbumDiscoveryCache(
	albumId: string,
	data: Omit<AlbumDiscoveryCache, 'timestamp'>
) {
	albumCache.set(albumId, { ...data, timestamp: Date.now() });
}
