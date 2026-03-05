export type SourceType = 'jellyfin' | 'local' | 'youtube';

export function getSourceLabel(sourceType: string): string {
	if (sourceType === 'local') return 'Local';
	if (sourceType === 'jellyfin') return 'Jellyfin';
	if (sourceType === 'youtube') return 'YouTube';
	return 'Unknown';
}

export function getSourceColor(sourceType: string): string {
	if (sourceType === 'jellyfin') return 'rgb(var(--brand-jellyfin))';
	if (sourceType === 'local') return 'rgb(var(--brand-localfiles))';
	if (sourceType === 'youtube') return 'var(--color-youtube)';
	return 'currentColor';
}
