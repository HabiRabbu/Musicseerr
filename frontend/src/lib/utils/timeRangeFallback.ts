import type { HomeAlbum, HomeArtist } from '$lib/types';

export type TimeRangeItemType = 'album' | 'artist';

export function getTimeRangeFallbackPath(
	itemType: TimeRangeItemType,
	item: HomeAlbum | HomeArtist
): string | null {
	if (itemType === 'album') {
		const album = item as HomeAlbum;
		const query = [album.artist_name, album.name].filter(Boolean).join(' ').trim();
		return query ? `/search/albums?q=${encodeURIComponent(query)}` : null;
	}

	const query = item.name?.trim();
	return query ? `/search/artists?q=${encodeURIComponent(query)}` : null;
}
