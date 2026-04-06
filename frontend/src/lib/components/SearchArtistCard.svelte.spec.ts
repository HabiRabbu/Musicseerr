import { page } from '@vitest/browser/context';
import { describe, expect, it } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SearchArtistCard from './SearchArtistCard.svelte';
import type { Artist, EnrichmentSource } from '$lib/types';

const baseArtist: Artist = {
	title: 'Radiohead',
	musicbrainz_id: 'a74b1b7f-71a5-4011-9441-d0b5e4122711',
	in_library: false,
	disambiguation: 'English rock band',
	release_group_count: 9,
	listen_count: 2500000
};

function renderComponent(
	overrides: Partial<{ artist: Artist; enrichmentSource: EnrichmentSource }> = {}
) {
	return render(SearchArtistCard, {
		props: {
			artist: overrides.artist ?? baseArtist,
			enrichmentSource: overrides.enrichmentSource ?? 'none'
		}
	} as Parameters<typeof render<typeof SearchArtistCard>>[1]);
}

describe('SearchArtistCard.svelte', () => {
	it('should display the artist name', async () => {
		renderComponent();
		await expect.element(page.getByText('Radiohead')).toBeInTheDocument();
	});

	it('should display release count badge', async () => {
		renderComponent();
		await expect.element(page.getByText('9 releases')).toBeInTheDocument();
	});

	it('should show Last.fm branded badge when source is lastfm', async () => {
		renderComponent({ enrichmentSource: 'lastfm' });

		const badge = page.getByTitle('Last.fm listeners');
		await expect.element(badge).toBeInTheDocument();
		await expect.element(page.getByText(/Last\.fm/)).toBeInTheDocument();
	});

	it('should show ListenBrainz branded badge when source is listenbrainz', async () => {
		renderComponent({ enrichmentSource: 'listenbrainz' });

		const badge = page.getByTitle('ListenBrainz plays');
		await expect.element(badge).toBeInTheDocument();
		await expect.element(page.getByText(/LB/)).toBeInTheDocument();
	});

	it('should show generic badge when source is none', async () => {
		renderComponent({ enrichmentSource: 'none' });

		const badge = page.getByTitle('Plays');
		await expect.element(badge).toBeInTheDocument();

		await expect.element(page.getByText(/Last\.fm/)).not.toBeInTheDocument();
		await expect.element(page.getByText(/\bLB\b/)).not.toBeInTheDocument();
	});

	it('should not render listen count badge when listen_count is null', async () => {
		renderComponent({
			artist: { ...baseArtist, listen_count: null },
			enrichmentSource: 'lastfm'
		});

		await expect.element(page.getByTitle('Last.fm listeners')).not.toBeInTheDocument();
	});

	it('should render zero listen count as "0"', async () => {
		renderComponent({
			artist: { ...baseArtist, listen_count: 0 },
			enrichmentSource: 'lastfm'
		});

		const badge = page.getByTitle('Last.fm listeners');
		await expect.element(badge).toBeInTheDocument();
		await expect.element(page.getByText('Last.fm 0')).toBeInTheDocument();
	});

	it('should display formatted count for large numbers', async () => {
		renderComponent({ enrichmentSource: 'lastfm' });

		await expect.element(page.getByText('Last.fm 2.5M')).toBeInTheDocument();
	});

	it('should display disambiguation when present', async () => {
		renderComponent();
		await expect.element(page.getByText('English rock band')).toBeInTheDocument();
	});

	it('should singular release for count of 1', async () => {
		renderComponent({
			artist: { ...baseArtist, release_group_count: 1 }
		});
		await expect.element(page.getByText('1 release')).toBeInTheDocument();
	});
});
