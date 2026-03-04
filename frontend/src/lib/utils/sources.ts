export type SourceType = 'jellyfin' | 'howler' | 'youtube';

export function getSourceLabel(sourceType: string): string {
	if (sourceType === 'howler') return 'Local';
	if (sourceType === 'jellyfin') return 'Jellyfin';
	if (sourceType === 'youtube') return 'YouTube';
	return 'Unknown';
}

export function getSourceColor(sourceType: string): string {
	if (sourceType === 'jellyfin') return 'rgb(var(--brand-jellyfin))';
	if (sourceType === 'howler') return 'rgb(var(--brand-localfiles))';
	if (sourceType === 'youtube') return 'var(--color-youtube)';
	return 'currentColor';
}
