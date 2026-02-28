import { resolve } from '$app/paths';

export function albumHref(mbid: string): string {
	return resolve('/album/[id]', { id: mbid });
}

export function artistHref(mbid: string): string {
	return resolve('/artist/[id]', { id: mbid });
}

export function albumHrefOrNull(mbid: string | null | undefined): string | null {
	return mbid ? albumHref(mbid) : null;
}

export function artistHrefOrNull(mbid: string | null | undefined): string | null {
	return mbid ? artistHref(mbid) : null;
}
