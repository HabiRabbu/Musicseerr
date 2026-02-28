import { CACHE_KEYS, CACHE_TTL } from '$lib/constants';
import type { ArtistInfo, LastFmArtistEnrichment } from '$lib/types';
import { createLocalStorageCache } from '$lib/utils/localStorageCache';

const MAX_ARTIST_DETAIL_CACHE_ENTRIES = 120;

export type ArtistExtendedCachePayload = {
	description: string | null;
	image: string | null;
};

export const artistBasicCache = createLocalStorageCache<ArtistInfo>(
	CACHE_KEYS.ARTIST_BASIC_CACHE,
	CACHE_TTL.ARTIST_DETAIL_BASIC,
	{ maxEntries: MAX_ARTIST_DETAIL_CACHE_ENTRIES }
);

export const artistExtendedCache = createLocalStorageCache<ArtistExtendedCachePayload>(
	CACHE_KEYS.ARTIST_EXTENDED_CACHE,
	CACHE_TTL.ARTIST_DETAIL_EXTENDED,
	{ maxEntries: MAX_ARTIST_DETAIL_CACHE_ENTRIES }
);

export const artistLastFmCache = createLocalStorageCache<LastFmArtistEnrichment>(
	CACHE_KEYS.ARTIST_LASTFM_CACHE,
	CACHE_TTL.ARTIST_DETAIL_LASTFM,
	{ maxEntries: MAX_ARTIST_DETAIL_CACHE_ENTRIES }
);
