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

export type LibraryAlbum = {
	artist: string;
	album: string;
	year?: number | null;
	monitored: boolean;
	quality?: string | null;
	cover_url?: string | null;
	musicbrainz_id?: string | null;
	artist_mbid?: string | null;
	date_added?: number | null;
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
	image?: string | null;
	tags: string[];
	aliases: string[];
	external_links: ExternalLink[];
	in_library: boolean;
	albums: ReleaseGroup[];
	singles: ReleaseGroup[];
	eps: ReleaseGroup[];
	release_group_count?: number;
};

export type ArtistReleases = {
	albums: ReleaseGroup[];
	singles: ReleaseGroup[];
	eps: ReleaseGroup[];
	total_count: number;
	has_more: boolean;
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
	length?: number | null;
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
	total_length?: number | null;
	in_library: boolean;
};

export type LidarrConnectionSettings = {
	lidarr_url: string;
	lidarr_api_key: string;
	quality_profile_id: number;
	metadata_profile_id: number;
	root_folder_path: string;
};

export type SoularrConnectionSettings = {
	soularr_url: string;
	soularr_api_key: string;
	trigger_soularr: boolean;
};

export type JellyfinConnectionSettings = {
	jellyfin_url: string;
};

export type QualityProfile = {
	id: number;
	name: string;
};

export type MetadataProfile = {
	id: number;
	name: string;
};

export type RootFolder = {
	id: string;
	path: string;
};

export type LidarrVerifyResponse = {
	success: boolean;
	message: string;
	quality_profiles: QualityProfile[];
	metadata_profiles: MetadataProfile[];
	root_folders: RootFolder[];
};