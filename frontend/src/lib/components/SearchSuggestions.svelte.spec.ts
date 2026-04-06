import { page, userEvent } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SearchSuggestions from './SearchSuggestions.svelte';
import type { SuggestResult } from '$lib/types';

const mockResults: SuggestResult[] = [
	{
		type: 'artist',
		title: 'Muse',
		artist: null,
		year: null,
		musicbrainz_id: 'artist-1',
		in_library: true,
		requested: false,
		score: 95
	},
	{
		type: 'album',
		title: 'Origin of Symmetry',
		artist: 'Muse',
		year: 2001,
		musicbrainz_id: 'album-1',
		in_library: false,
		requested: true,
		score: 90
	}
];

function makeResponse(body: unknown, status = 200): Response {
	const json = JSON.stringify(body);
	return new Response(json, {
		status,
		headers: { 'Content-Type': 'application/json' }
	});
}

function mockFetchSuccess(results: SuggestResult[] = mockResults) {
	return vi.fn().mockImplementation(() => Promise.resolve(makeResponse({ results })));
}

function mockFetchError() {
	return vi
		.fn()
		.mockImplementation(() =>
			Promise.resolve(makeResponse({ error: 'Internal Server Error' }, 500))
		);
}

function renderComponent(props: Record<string, unknown> = {}) {
	const options = {
		props: { query: '', onSearch: vi.fn(), onSelect: vi.fn(), ...props }
	};
	return render(
		SearchSuggestions,
		options as unknown as Parameters<typeof render<typeof SearchSuggestions>>[1]
	);
}

describe('SearchSuggestions.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
		vi.useFakeTimers({ shouldAdvanceTime: true });
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
		vi.useRealTimers();
	});

	it('should render the search input', async () => {
		renderComponent();

		const input = page.getByRole('searchbox');
		await expect.element(input).toBeInTheDocument();
	});

	it('should not show dropdown for short input', async () => {
		renderComponent({ query: 'a' });

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).not.toBeInTheDocument();
	});

	it('should show dropdown with suggestions after typing', async () => {
		globalThis.fetch = mockFetchSuccess();

		renderComponent();

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).toBeInTheDocument();

		const options = page.getByRole('option');
		await expect.element(options.first()).toBeInTheDocument();
	});

	it('should call onSelect when clicking a suggestion', async () => {
		globalThis.fetch = mockFetchSuccess();

		const onSelect = vi.fn();
		renderComponent({ onSelect });

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const firstOption = page.getByRole('option').first();
		await firstOption.click();

		expect(onSelect).toHaveBeenCalledWith(mockResults[0]);
	});

	it('should call onSearch on form submit (Enter)', async () => {
		const onSearch = vi.fn();
		renderComponent({ query: 'test', onSearch });

		const input = page.getByRole('searchbox');
		await input.click();
		await userEvent.keyboard('{Enter}');

		expect(onSearch).toHaveBeenCalled();
	});

	it('should hide dropdown on Escape', async () => {
		globalThis.fetch = mockFetchSuccess();

		renderComponent();

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).toBeInTheDocument();

		await input.click();
		await userEvent.keyboard('{Escape}');
		await expect.element(listbox).not.toBeInTheDocument();
	});

	it('should hide dropdown on fetch error', async () => {
		globalThis.fetch = mockFetchError();

		renderComponent();

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).not.toBeInTheDocument();
	});

	it('should show View all results link', async () => {
		globalThis.fetch = mockFetchSuccess();

		const onSearch = vi.fn();
		renderComponent({ onSearch });

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const viewAll = page.getByText('View all results');
		await expect.element(viewAll).toBeInTheDocument();

		await viewAll.click();
		expect(onSearch).toHaveBeenCalled();
	});

	it('should debounce and only fire one fetch for rapid input', async () => {
		const fetchSpy = mockFetchSuccess();
		globalThis.fetch = fetchSpy;

		renderComponent();

		const input = page.getByRole('searchbox');
		await input.fill('m');
		await vi.advanceTimersByTimeAsync(100);
		await input.fill('mu');
		await vi.advanceTimersByTimeAsync(100);
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		expect(fetchSpy).toHaveBeenCalledTimes(1);
	});

	it('should use custom id for listbox', async () => {
		globalThis.fetch = mockFetchSuccess();

		renderComponent({ id: 'custom-test' });

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).toHaveAttribute('id', 'custom-test-listbox');
	});

	it('should ignore stale responses when a newer request is pending', async () => {
		let callCount = 0;
		globalThis.fetch = vi.fn().mockImplementation(() => {
			callCount++;
			const currentCall = callCount;
			if (currentCall === 1) {
				return new Promise((resolve) =>
					setTimeout(
						() =>
							resolve(
								makeResponse({
									results: [
										{
											type: 'artist' as const,
											title: 'StaleResult',
											musicbrainz_id: 'stale-1',
											in_library: false,
											score: 50
										}
									]
								})
							),
						300
					)
				);
			}
			return Promise.resolve(
				makeResponse({
					results: [
						{
							type: 'artist' as const,
							title: 'FreshResult',
							musicbrainz_id: 'fresh-1',
							in_library: false,
							score: 80
						}
					]
				})
			);
		});

		renderComponent();

		const input = page.getByRole('searchbox');

		await input.fill('ab');
		await vi.advanceTimersByTimeAsync(600);

		await input.fill('abc');
		await vi.advanceTimersByTimeAsync(600);

		await vi.advanceTimersByTimeAsync(700);

		const stale = page.getByText('StaleResult');
		await expect.element(stale).not.toBeInTheDocument();

		const fresh = page.getByText('FreshResult');
		await expect.element(fresh).toBeInTheDocument();
	});

	it('should render combobox with correct ARIA attributes', async () => {
		globalThis.fetch = mockFetchSuccess();

		renderComponent({ id: 'aria-test' });

		const combobox = page.getByRole('combobox');
		await expect.element(combobox).toHaveAttribute('aria-haspopup', 'listbox');
		await expect.element(combobox).toHaveAttribute('aria-expanded', 'false');

		const input = page.getByRole('searchbox');
		await expect.element(input).toHaveAttribute('aria-autocomplete', 'list');
		await expect.element(input).toHaveAttribute('aria-controls', 'aria-test-listbox');

		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		await expect.element(combobox).toHaveAttribute('aria-expanded', 'true');

		const options = page.getByRole('option');
		await expect.element(options.first()).toHaveAttribute('aria-selected', 'false');
	});

	it('should hide dropdown on click outside', async () => {
		globalThis.fetch = mockFetchSuccess();

		renderComponent();

		const input = page.getByRole('searchbox');
		await input.fill('mus');
		await vi.advanceTimersByTimeAsync(700);

		const listbox = page.getByRole('listbox');
		await expect.element(listbox).toBeInTheDocument();

		await document.body.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true }));

		await expect.element(listbox).not.toBeInTheDocument();
	});
});
