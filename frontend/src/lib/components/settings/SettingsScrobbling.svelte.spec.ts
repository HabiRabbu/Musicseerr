import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SettingsScrobbling from './SettingsScrobbling.svelte';
import { integrationStore } from '$lib/stores/integration';

function mockScrobbleSettings(
	overrides: { scrobble_to_lastfm?: boolean; scrobble_to_listenbrainz?: boolean } = {}
) {
	return {
		scrobble_to_lastfm: false,
		scrobble_to_listenbrainz: false,
		...overrides,
	};
}

describe('SettingsScrobbling.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
		integrationStore.reset();
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
		integrationStore.reset();
	});

	it('renders heading', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		render(SettingsScrobbling);

		const heading = page.getByRole('heading', { name: 'Scrobbling' });
		await expect.element(heading).toBeInTheDocument();
	});

	it('shows loading spinner initially', async () => {
		globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		const { container } = render(SettingsScrobbling);

		await vi.waitFor(() => {
			const spinners = container.querySelectorAll('.loading');
			expect(spinners.length).toBeGreaterThan(0);
		});
	});

	it('renders both scrobble toggles after load', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		render(SettingsScrobbling);

		const lastfmLabel = page.getByText('Scrobble to Last.fm');
		const lbLabel = page.getByText('Scrobble to ListenBrainz');

		await expect.element(lastfmLabel).toBeInTheDocument();
		await expect.element(lbLabel).toBeInTheDocument();
	});

	it('disables Last.fm toggle when Last.fm is not connected', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: false, listenbrainz: true });
		render(SettingsScrobbling);

		await vi.waitFor(async () => {
			const toggles = document.querySelectorAll('input[type="checkbox"].toggle');
			const lastfmToggle = toggles[0] as HTMLInputElement;
			expect(lastfmToggle.disabled).toBe(true);
		});
	});

	it('disables ListenBrainz toggle when LB is not connected', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: false });
		render(SettingsScrobbling);

		await vi.waitFor(async () => {
			const toggles = document.querySelectorAll('input[type="checkbox"].toggle');
			const lbToggle = toggles[1] as HTMLInputElement;
			expect(lbToggle.disabled).toBe(true);
		});
	});

	it('enables both toggles when both services are connected', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		render(SettingsScrobbling);

		await vi.waitFor(async () => {
			const toggles = document.querySelectorAll('input[type="checkbox"].toggle');
			expect(toggles.length).toBe(2);
			expect((toggles[0] as HTMLInputElement).disabled).toBe(false);
			expect((toggles[1] as HTMLInputElement).disabled).toBe(false);
		});
	});

	it('renders save button', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		render(SettingsScrobbling);

		const saveBtn = page.getByRole('button', { name: 'Save Settings' });
		await expect.element(saveBtn).toBeInTheDocument();
	});

	it('shows "not connected" hint when service is disconnected', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve(mockScrobbleSettings()),
		});
		integrationStore.setStatus({ lastfm: false, listenbrainz: false });
		render(SettingsScrobbling);

		const notConnected = page.getByText('Last.fm is not connected');
		await expect.element(notConnected).toBeInTheDocument();

		const lbNotConnected = page.getByText('ListenBrainz is not connected');
		await expect.element(lbNotConnected).toBeInTheDocument();
	});

	it('shows error message when load fails', async () => {
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: false,
			status: 500,
			json: () => Promise.reject(new Error('Server error')),
		});
		integrationStore.setStatus({ lastfm: true, listenbrainz: true });
		render(SettingsScrobbling);

		const errorAlert = page.getByText('Failed to load scrobble settings');
		await expect.element(errorAlert).toBeInTheDocument();
	});
});
