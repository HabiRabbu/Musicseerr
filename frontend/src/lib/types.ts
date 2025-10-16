export type Artist = {
	title: string;                 // Artist name
	musicbrainz_id: string;
	in_library: boolean;
	cover_url?: string | null;
};

export type Album = {
	title: string;
	artist: string | null;
	year: number | null;
	musicbrainz_id: string;        // Release group ID
	in_library: boolean;
	cover_url?: string | null;
};

export type SearchResults = {
	artists: Artist[];
	albums: Album[];
};