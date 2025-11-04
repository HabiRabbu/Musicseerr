export type Artist = {
	title: string;                 
	musicbrainz_id: string;
	in_library: boolean;
	cover_url?: string | null;
};

export type Album = {
	title: string;
	artist: string | null;
	year: number | null;
	musicbrainz_id: string;        
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

export type UserPreferences = {
	primary_types: string[];
	secondary_types: string[];
	release_statuses: string[];
};

export type ReleaseTypeOption = {
	id: string;
	title: string;
	description: string;
};

export type Track = {
	position: number;
	title: string;
	length?: number | null;  // Length in milliseconds
	recording_id?: string | null;
};

export type AlbumInfo = {
	title: string;
	musicbrainz_id: string;
	artist_name: string;
	artist_id: string;
	release_date?: string | null;
	year?: number | null;
	type?: string | null;
	label?: string | null;
	barcode?: string | null;
	country?: string | null;
	disambiguation?: string | null;
	tracks: Track[];
	total_tracks: number;
	total_length?: number | null;  // Total length in milliseconds
	in_library: boolean;
};