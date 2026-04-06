import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SourceSwitcher from './SourceSwitcher.svelte';
import { integrationStore } from '$lib/stores/integration';
import { musicSourceStore, type MusicSource } from '$lib/stores/musicSource';
import { PAGE_SOURCE_KEYS } from '$lib/constants';

describe('SourceSwitcher.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
		globalThis.fetch = vi.fn().mockResolvedValue({
			ok: true,
			json: () => Promise.resolve({ source: 'listenbrainz' })
		});
		integrationStore.reset();
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
		integrationStore.reset();
		localStorage.removeItem(PAGE_SOURCE_KEYS.home);
	});

	it('renders nothing when only ListenBrainz is enabled', async () => {
		integrationStore.setStatus({ listenbrainz: true, lastfm: false });
		const { container } = render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);
		await vi.waitFor(() => {
			const buttons = container.querySelectorAll('button');
			expect(buttons.length).toBe(0);
		});
	});

	it('renders nothing when only Last.fm is enabled', async () => {
		integrationStore.setStatus({ listenbrainz: false, lastfm: true });
		const { container } = render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);
		await vi.waitFor(() => {
			const buttons = container.querySelectorAll('button');
			expect(buttons.length).toBe(0);
		});
	});

	it('renders nothing when neither service is enabled', async () => {
		integrationStore.setStatus({ listenbrainz: false, lastfm: false });
		const { container } = render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);
		await vi.waitFor(() => {
			const buttons = container.querySelectorAll('button');
			expect(buttons.length).toBe(0);
		});
	});

	it('renders switcher buttons when both services are enabled', async () => {
		integrationStore.setStatus({ listenbrainz: true, lastfm: true });
		render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);

		const lbBtn = page.getByRole('button', { name: 'ListenBrainz' });
		const lfmBtn = page.getByRole('button', { name: 'Last.fm' });

		await expect.element(lbBtn).toBeInTheDocument();
		await expect.element(lfmBtn).toBeInTheDocument();
	});

	it('defaults to ListenBrainz as active source', async () => {
		integrationStore.setStatus({ listenbrainz: true, lastfm: true });
		render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);

		const lbBtn = page.getByRole('button', { name: 'ListenBrainz' });
		await vi.waitFor(async () => {
			const el = lbBtn.element();
			expect(el.className).toContain('btn-primary');
		});
	});

	it('calls onSourceChange when switching source', async () => {
		integrationStore.setStatus({ listenbrainz: true, lastfm: true });
		const onSourceChange = vi.fn<(source: MusicSource) => void>();
		render(SourceSwitcher, {
			props: { pageKey: 'home', onSourceChange }
		} as unknown as Parameters<typeof render<typeof SourceSwitcher>>[1]);

		const lfmBtn = page.getByRole('button', { name: 'Last.fm' });
		await lfmBtn.click();

		await vi.waitFor(() => {
			expect(onSourceChange).toHaveBeenCalledWith('lastfm');
		});
	});

	it('updates page source when switching source', async () => {
		integrationStore.setStatus({ listenbrainz: true, lastfm: true });

		render(SourceSwitcher, {
			props: { pageKey: 'home' }
		} as Parameters<typeof render<typeof SourceSwitcher>>[1]);

		const lfmBtn = page.getByRole('button', { name: 'Last.fm' });
		await lfmBtn.click();

		await vi.waitFor(() => {
			expect(musicSourceStore.getPageSource('home')).toBe('lastfm');
		});
	});
});
