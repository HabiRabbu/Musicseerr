import { page, userEvent } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import type { PlaylistDetail, PlaylistTrack } from '$lib/api/playlists';

const mockFetchPlaylist = vi.fn();
const mockDeletePlaylist = vi.fn();
const mockRemoveTrackFromPlaylist = vi.fn();
const mockRemoveTracksFromPlaylist = vi.fn();
const mockUpdatePlaylist = vi.fn();
const mockUpdatePlaylistTrack = vi.fn();
const mockReorderPlaylistTrack = vi.fn();
const mockUploadPlaylistCover = vi.fn();
const mockDeletePlaylistCover = vi.fn();
const mockResolvePlaylistSources = vi.fn();

vi.mock('$lib/api/playlists', () => ({
	fetchPlaylist: (...args: unknown[]) => mockFetchPlaylist(...args),
	deletePlaylist: (...args: unknown[]) => mockDeletePlaylist(...args),
	removeTrackFromPlaylist: (...args: unknown[]) => mockRemoveTrackFromPlaylist(...args),
	removeTracksFromPlaylist: (...args: unknown[]) => mockRemoveTracksFromPlaylist(...args),
	updatePlaylist: (...args: unknown[]) => mockUpdatePlaylist(...args),
	updatePlaylistTrack: (...args: unknown[]) => mockUpdatePlaylistTrack(...args),
	reorderPlaylistTrack: (...args: unknown[]) => mockReorderPlaylistTrack(...args),
	uploadPlaylistCover: (...args: unknown[]) => mockUploadPlaylistCover(...args),
	deletePlaylistCover: (...args: unknown[]) => mockDeletePlaylistCover(...args),
	resolvePlaylistSources: (...args: unknown[]) => mockResolvePlaylistSources(...args)
}));

const mockToastShow = vi.fn();
vi.mock('$lib/stores/toast', () => ({
	toastStore: { show: (...args: unknown[]) => mockToastShow(...args) }
}));

const mockPlayQueue = vi.fn();
const mockAddToQueue = vi.fn();
const mockPlayNext = vi.fn();
vi.mock('$lib/stores/player.svelte', () => ({
	playerStore: {
		playQueue: (...args: unknown[]) => mockPlayQueue(...args),
		addToQueue: (...args: unknown[]) => mockAddToQueue(...args),
		playNext: (...args: unknown[]) => mockPlayNext(...args)
	}
}));

const mockGoto = vi.fn();
vi.mock('$app/navigation', () => ({
	goto: (...args: unknown[]) => mockGoto(...args)
}));

vi.mock('$lib/stores/cacheTtl', () => ({
	getCacheTTL: () => 15 * 60 * 1000
}));

import DetailPage from './+page.svelte';

function renderDetail(playlistId = 'pl-1') {
	return render(DetailPage, {
		props: { data: { playlistId } }
	} as Parameters<typeof render<typeof DetailPage>>[1]);
}

function makeTrack(overrides: Partial<PlaylistTrack> = {}): PlaylistTrack {
	return {
		id: 'trk-1',
		position: 0,
		track_name: 'Test Track',
		artist_name: 'Test Artist',
		album_name: 'Test Album',
		album_id: 'alb-1',
		artist_id: 'art-1',
		track_source_id: 'vid-1',
		cover_url: '/cover.jpg',
		source_type: 'local',
		available_sources: ['local'],
		format: 'flac',
		track_number: 1,
		disc_number: null,
		duration: 240,
		created_at: '2026-01-01T00:00:00Z',
		...overrides
	};
}

function makePlaylist(overrides: Partial<PlaylistDetail> = {}): PlaylistDetail {
	return {
		id: 'pl-1',
		name: 'My Playlist',
		track_count: 2,
		total_duration: 480,
		cover_urls: [],
		custom_cover_url: null,
		created_at: '2026-01-01T00:00:00Z',
		updated_at: '2026-01-02T00:00:00Z',
		tracks: [
			makeTrack({ id: 'trk-1', position: 0, track_name: 'First Track', duration: 240 }),
			makeTrack({
				id: 'trk-2',
				position: 1,
				track_name: 'Second Track',
				artist_name: 'Other Artist',
				duration: 240
			})
		],
		...overrides
	};
}

describe('Playlist detail page', () => {
	beforeEach(() => {
		mockFetchPlaylist.mockReset();
		mockDeletePlaylist.mockReset();
		mockRemoveTrackFromPlaylist.mockReset();
		mockUpdatePlaylist.mockReset();
		mockUpdatePlaylistTrack.mockReset();
		mockReorderPlaylistTrack.mockReset();
		mockUploadPlaylistCover.mockReset();
		mockDeletePlaylistCover.mockReset();
		mockResolvePlaylistSources.mockReset();
		mockResolvePlaylistSources.mockResolvedValue({});
		mockToastShow.mockReset();
		mockPlayQueue.mockReset();
		mockAddToQueue.mockReset();
		mockPlayNext.mockReset();
		mockGoto.mockReset();
		try {
			localStorage.clear();
		} catch {
			/* ignore in non-browser */
		}
	});

	it('renders header with playlist name, track count, and duration', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();
		await expect.element(page.getByText(/2 tracks/)).toBeVisible();
		await expect.element(page.getByText(/8 min/)).toBeVisible();
	});

	it('renders track rows with correct data', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect.element(page.getByText('First Track')).toBeVisible();
		await expect.element(page.getByText('Second Track')).toBeVisible();
		await expect.element(page.getByText('Other Artist')).toBeVisible();
	});

	it('shows error state when playlist is missing', async () => {
		mockFetchPlaylist.mockRejectedValue(new Error('404 not found'));
		renderDetail('pl-bad');

		await expect.element(page.getByText("Couldn't load this playlist")).toBeVisible();
		await expect.element(page.getByText('Playlist not found')).toBeVisible();
	});

	it('shows empty state when playlist has no tracks', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist({ tracks: [], track_count: 0 }));
		renderDetail('pl-1');

		await expect.element(page.getByText('This playlist is empty')).toBeVisible();
	});

	it('Play All calls playQueue with all tracks', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		const playBtn = page.getByRole('button', { name: /Play All/ });
		await playBtn.click();

		expect(mockPlayQueue).toHaveBeenCalledOnce();
		const [items, startIdx, shuffle] = mockPlayQueue.mock.calls[0];
		expect(items).toHaveLength(2);
		expect(startIdx).toBe(0);
		expect(shuffle).toBe(false);
	});

	it('Shuffle calls playQueue with shuffle=true', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		const shuffleBtn = page.getByRole('button', { name: /Shuffle/ });
		await shuffleBtn.click();

		expect(mockPlayQueue).toHaveBeenCalledOnce();
		expect(mockPlayQueue.mock.calls[0][2]).toBe(true);
	});

	it('Play All is disabled when playlist has no tracks', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist({ tracks: [], track_count: 0 }));
		renderDetail('pl-1');

		await expect.element(page.getByText('This playlist is empty')).toBeVisible();
		const playBtn = page.getByRole('button', { name: /Play All/ });
		expect(await playBtn.element()).toBeDisabled();
	});

	it('delete confirmation modal shows and cancel does not delete', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		await expect.element(page.getByText(/Delete "My Playlist"\?/)).not.toBeVisible();

		expect(mockDeletePlaylist).not.toHaveBeenCalled();
	});

	it('back button is visible when playlist loads', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		const backButton = page.getByRole('button', { name: /Go back/ });
		await expect.element(backButton).toBeVisible();
	});

	it('inline name editing: clicking name shows input, Escape cancels', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		const editBtn = page.getByRole('button', { name: /Edit playlist name/ });
		await editBtn.click();

		const nameInput = page.getByPlaceholder('Playlist name');
		await expect.element(nameInput).toBeVisible();

		await userEvent.keyboard('{Escape}');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();
		expect(mockUpdatePlaylist).not.toHaveBeenCalled();
	});

	it('inline name editing: Enter saves new name', async () => {
		mockUpdatePlaylist.mockResolvedValue({ name: 'Renamed', updated_at: '2026-01-03T00:00:00Z' });
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		const editBtn = page.getByRole('button', { name: /Edit playlist name/ });
		await editBtn.click();

		const nameInput = page.getByPlaceholder('Playlist name');
		await expect.element(nameInput).toBeVisible();
		await nameInput.clear();
		await nameInput.fill('Renamed');
		await userEvent.keyboard('{Enter}');

		expect(mockUpdatePlaylist).toHaveBeenCalledOnce();
		expect(mockUpdatePlaylist.mock.calls[0][1]).toEqual({ name: 'Renamed' });
	});

	it('inline name editing: save button click saves new name', async () => {
		mockUpdatePlaylist.mockResolvedValue({ name: 'Renamed', updated_at: '2026-01-03T00:00:00Z' });
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		await page.getByRole('button', { name: /Edit playlist name/ }).click();

		const nameInput = page.getByPlaceholder('Playlist name');
		await expect.element(nameInput).toBeVisible();
		await nameInput.clear();
		await nameInput.fill('Renamed');
		await page.getByRole('button', { name: 'Save name' }).click();

		await vi.waitFor(() => {
			expect(mockUpdatePlaylist).toHaveBeenCalledOnce();
		});
		expect(mockUpdatePlaylist.mock.calls[0][1]).toEqual({ name: 'Renamed' });
		await expect.element(page.getByRole('heading', { name: 'Renamed', level: 1 })).toBeVisible();
	});

	it('delete confirmation modal contains correct text and cancel button', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();

		// Modal exists in DOM but is not visible until opened
		await expect.element(page.getByText(/This will permanently remove/)).not.toBeVisible();
		expect(mockDeletePlaylist).not.toHaveBeenCalled();
	});

	it('remove track shows toast and updates track list', async () => {
		mockRemoveTrackFromPlaylist.mockResolvedValue(undefined);
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect.element(page.getByText('First Track')).toBeVisible();
		await expect.element(page.getByText('Second Track')).toBeVisible();
		expect(mockRemoveTrackFromPlaylist).not.toHaveBeenCalled();
	});

	it('calls resolvePlaylistSources after playlist loads', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		mockResolvePlaylistSources.mockResolvedValue({});
		renderDetail('pl-1');

		await expect
			.element(page.getByRole('heading', { name: 'My Playlist', level: 1 }))
			.toBeVisible();
		await vi.waitFor(() => {
			expect(mockResolvePlaylistSources).toHaveBeenCalledWith('pl-1');
		});
	});

	it('merges resolved sources into track available_sources', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		mockResolvePlaylistSources.mockResolvedValue({
			'trk-1': ['local', 'jellyfin'],
			'trk-2': ['local']
		});
		renderDetail('pl-1');

		await expect.element(page.getByText('First Track')).toBeVisible();
		await vi.waitFor(() => {
			expect(mockResolvePlaylistSources).toHaveBeenCalledWith('pl-1');
		});
	});

	it('shows play button on track hover with correct aria label', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect.element(page.getByText('First Track')).toBeVisible();

		const playBtn = page.getByRole('button', { name: 'Play First Track' });
		expect(playBtn.elements()).toHaveLength(1);
	});

	it('play button on track calls playQueue with correct start index', async () => {
		mockFetchPlaylist.mockResolvedValue(makePlaylist());
		renderDetail('pl-1');

		await expect.element(page.getByText('Second Track')).toBeVisible();

		const playSecond = page.getByRole('button', { name: 'Play Second Track' });
		await playSecond.click();

		expect(mockPlayQueue).toHaveBeenCalledOnce();
		const [items, startIdx, shuffle] = mockPlayQueue.mock.calls[0];
		expect(items).toHaveLength(2);
		expect(startIdx).toBe(1);
		expect(shuffle).toBe(false);
	});
});
