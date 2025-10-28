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

export type ReleaseGroup = {
	id: string;
	title: string;
	type?: string;
	year?: number;
	first_release_date?: string;
	in_library: boolean;
};

export type ExternalLink = {
	type: string;
	url: string;
	label: string;
};

export type ArtistInfo = {
	name: string;
	musicbrainz_id: string;
	disambiguation?: string | null;
	type?: string | null;
	country?: string | null;
	life_span?: {
		begin?: string | null;
		end?: string | null;
		ended?: boolean;
	} | null;
	description?: string | null;
	tags: string[];
	aliases: string[];
	external_links: ExternalLink[];
	in_library: boolean;
	albums: ReleaseGroup[];
	singles: ReleaseGroup[];
	eps: ReleaseGroup[];
};