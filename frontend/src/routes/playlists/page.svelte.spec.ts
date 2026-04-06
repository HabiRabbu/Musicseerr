import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import type { PlaylistSummary } from '$lib/api/playlists';

const mockFetchPlaylists = vi.fn();
const mockCreatePlaylist = vi.fn();
const mockFetchPlaylist = vi.fn();
const mockDeletePlaylist = vi.fn();

vi.mock('$lib/api/playlists', () => ({
	fetchPlaylists: (...args: unknown[]) => mockFetchPlaylists(...args),
	createPlaylist: (...args: unknown[]) => mockCreatePlaylist(...args),
	fetchPlaylist: (...args: unknown[]) => mockFetchPlaylist(...args),
	deletePlaylist: (...args: unknown[]) => mockDeletePlaylist(...args),
	resolvePlaylistSources: vi.fn().mockResolvedValue({})
}));

const mockToastShow = vi.fn();
vi.mock('$lib/stores/toast', () => ({
	toastStore: { show: (...args: unknown[]) => mockToastShow(...args) }
}));

const mockGoto = vi.fn();
vi.mock('$app/navigation', () => ({
	goto: (...args: unknown[]) => mockGoto(...args)
}));

import PlaylistsPage from './+page.svelte';

function makePlaylist(overrides: Partial<PlaylistSummary> = {}): PlaylistSummary {
	return {
		id: 'pl-1',
		name: 'Test Playlist',
		track_count: 5,
		total_duration: 900,
		cover_urls: [],
		custom_cover_url: null,
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-02T00:00:00Z',
		...overrides
	};
}

describe('Playlists list page', () => {
	beforeEach(() => {
		mockFetchPlaylists.mockReset();
		mockCreatePlaylist.mockReset();
		mockToastShow.mockReset();
		mockGoto.mockReset();
	});

	it('renders playlist cards with correct data', async () => {
		expect.assertions(3);
		mockFetchPlaylists.mockResolvedValue([
			makePlaylist({ id: 'pl-1', name: 'Rock Mix', track_count: 10 }),
			makePlaylist({ id: 'pl-2', name: 'Chill Vibes', track_count: 3 })
		]);

		render(PlaylistsPage);

		await expect.element(page.getByText('Rock Mix')).toBeVisible();
		await expect.element(page.getByText('Chill Vibes')).toBeVisible();
		await expect.element(page.getByText(/10 tracks/)).toBeVisible();
	});

	it('renders empty state when no playlists exist', async () => {
		expect.assertions(2);
		mockFetchPlaylists.mockResolvedValue([]);

		render(PlaylistsPage);

		await expect.element(page.getByText('No playlists yet')).toBeVisible();
		await expect.element(page.getByText('Create your first playlist')).toBeVisible();
	});

	it('renders error state when fetch fails', async () => {
		expect.assertions(2);
		mockFetchPlaylists.mockRejectedValue(new Error('Server error'));

		render(PlaylistsPage);

		await expect.element(page.getByText('Server error')).toBeVisible();
		await expect.element(page.getByRole('button', { name: /Retry/ })).toBeVisible();
	});

	it('shows new playlist input when clicking New Playlist', async () => {
		expect.assertions(2);
		mockFetchPlaylists.mockResolvedValue([]);

		render(PlaylistsPage);

		await expect.element(page.getByText('No playlists yet')).toBeVisible();

		const newBtn = page.getByRole('button', { name: /New Playlist/ }).first();
		await newBtn.click();

		await expect.element(page.getByPlaceholder('Playlist name...')).toBeVisible();
	});

	it('page heading is visible', async () => {
		expect.assertions(1);
		mockFetchPlaylists.mockResolvedValue([]);

		render(PlaylistsPage);

		await expect.element(page.getByRole('heading', { name: 'Playlists' })).toBeVisible();
	});
});
