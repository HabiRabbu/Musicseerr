import type { QueueItem, SourceType } from '$lib/player/types';
import type { JellyfinTrackInfo, LocalTrackInfo } from '$lib/types';
import type { PlaylistTrack } from '$lib/api/playlists';
import { API } from '$lib/constants';
import { getCoverUrl } from '$lib/utils/errorHandling';

const SUPPORTED_CODECS = new Set(['aac', 'mp3', 'opus', 'flac', 'wav', 'wma', 'vorbis', 'alac']);
const CODEC_ALIASES: Record<string, string> = { alac: 'flac', wma: 'aac' };

function normalizeCodec(codec: string | undefined | null): string {
	const raw = codec?.toLowerCase() ?? 'aac';
	if (CODEC_ALIASES[raw]) return CODEC_ALIASES[raw];
	if (SUPPORTED_CODECS.has(raw)) return raw;
	return 'aac';
}

export interface TrackMeta {
	albumId: string;
	albumName: string;
	artistName: string;
	coverUrl: string | null;
	artistId?: string;
}

export interface TrackSourceData {
	trackPosition: number;
	trackTitle: string;
	trackLength?: number;
	jellyfinTrack?: JellyfinTrackInfo | null;
	localTrack?: LocalTrackInfo | null;
}

export function selectBestSource(
	data: TrackSourceData
): { sourceType: SourceType; trackSourceId: string; streamUrl: string; format?: string } | null {
	if (data.localTrack) {
		const format = data.localTrack.format.toLowerCase();
		return {
			sourceType: 'local',
			trackSourceId: String(data.localTrack.track_file_id),
			streamUrl: API.stream.local(data.localTrack.track_file_id),
			format
		};
	}
	if (data.jellyfinTrack) {
		const format = normalizeCodec(data.jellyfinTrack.codec);
		return {
			sourceType: 'jellyfin',
			trackSourceId: data.jellyfinTrack.jellyfin_id,
			streamUrl: API.stream.jellyfin(data.jellyfinTrack.jellyfin_id),
			format
		};
	}
	return null;
}

export function getAvailableSources(data: TrackSourceData): SourceType[] {
	const sources: SourceType[] = [];
	if (data.localTrack) sources.push('local');
	if (data.jellyfinTrack) sources.push('jellyfin');
	return sources;
}

export function buildQueueItem(meta: TrackMeta, data: TrackSourceData): QueueItem | null {
	const best = selectBestSource(data);
	if (!best) return null;

	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);

	return {
		trackSourceId: best.trackSourceId,
		trackName: data.trackTitle,
		artistName: meta.artistName,
		trackNumber: data.trackPosition,
		albumId: meta.albumId,
		albumName: meta.albumName,
		coverUrl: normalizedCoverUrl,
		sourceType: best.sourceType,
		artistId: meta.artistId,
		streamUrl: best.streamUrl,
		format: best.format,
		availableSources: getAvailableSources(data),
		duration: data.trackLength
	};
}

export function buildQueueItemsFromJellyfin(
	tracks: JellyfinTrackInfo[],
	meta: TrackMeta
): QueueItem[] {
	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);
	return tracks.map((t) => {
		const format = normalizeCodec(t.codec);
		return {
			trackSourceId: t.jellyfin_id,
			trackName: t.title,
			artistName: meta.artistName,
			trackNumber: t.track_number,
			albumId: meta.albumId,
			albumName: meta.albumName,
			coverUrl: normalizedCoverUrl,
			sourceType: 'jellyfin' as const,
			artistId: meta.artistId,
			streamUrl: API.stream.jellyfin(t.jellyfin_id),
			format,
			availableSources: ['jellyfin'] as SourceType[],
			duration: t.duration_seconds
		};
	});
}

export function buildQueueItemsFromLocal(
	tracks: LocalTrackInfo[],
	meta: TrackMeta
): QueueItem[] {
	const normalizedCoverUrl = getCoverUrl(meta.coverUrl, meta.albumId);
	return tracks.map((t) => ({
		trackSourceId: String(t.track_file_id),
		trackName: t.title,
		artistName: meta.artistName,
		trackNumber: t.track_number,
		albumId: meta.albumId,
		albumName: meta.albumName,
		coverUrl: normalizedCoverUrl,
		sourceType: 'local' as const,
		artistId: meta.artistId,
		streamUrl: API.stream.local(t.track_file_id),
		format: t.format.toLowerCase(),
		availableSources: ['local'] as SourceType[],
		duration: t.duration_seconds ?? undefined
	}));
}

function resolveStreamUrl(
	sourceType: string,
	trackSourceId: string,
	format?: string | null
): string | undefined {
	if (sourceType === 'local') return API.stream.local(trackSourceId);
	if (sourceType === 'jellyfin') return API.stream.jellyfin(trackSourceId);
	return undefined;
}

export function playlistTrackToQueueItem(track: PlaylistTrack): QueueItem | null {
	if (!track.track_source_id) return null;

	const sourceType = track.source_type as SourceType;
	const availableSources: SourceType[] = track.available_sources
		? (track.available_sources as SourceType[])
		: [sourceType];

	return {
		trackSourceId: track.track_source_id,
		trackName: track.track_name,
		artistName: track.artist_name,
		trackNumber: track.track_number ?? track.position,
		albumId: track.album_id ?? '',
		albumName: track.album_name,
		coverUrl: track.cover_url,
		sourceType,
		artistId: track.artist_id ?? undefined,
		streamUrl: resolveStreamUrl(sourceType, track.track_source_id, track.format),
		format: track.format ?? undefined,
		availableSources,
		duration: track.duration ?? undefined
	};
}
