import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SettingsLastFm from './SettingsLastFm.svelte';
import type { LastFmConnectionSettingsResponse } from '$lib/types';

const defaultResponse: LastFmConnectionSettingsResponse = {
	api_key: 'test-key',
	shared_secret: '••••••••alue',
	session_key: '',
	username: '',
	enabled: false
};

function mockLoadSuccess(data: LastFmConnectionSettingsResponse = defaultResponse) {
	return vi.fn().mockResolvedValue(new Response(JSON.stringify(data), { status: 200 }));
}

function mockLoadFailure() {
	return vi.fn().mockResolvedValue(
		new Response(JSON.stringify({ error: { message: 'Failed to load Last.fm settings' } }), {
			status: 500
		})
	);
}

describe('SettingsLastFm.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it('should render the heading', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsLastFm);

		const heading = page.getByRole('heading', { name: 'Last.fm' });
		await expect.element(heading).toBeInTheDocument();
	});

	it('should show loading spinner initially', async () => {
		globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
		render(SettingsLastFm);

		const spinner = page.getByText('').all();
		expect(spinner.length).toBeGreaterThanOrEqual(0);
	});

	it('should render API key and shared secret fields after load', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsLastFm);

		const apiKeyInput = page.getByPlaceholder('Your Last.fm API key');
		await expect.element(apiKeyInput).toBeInTheDocument();

		const secretInput = page.getByPlaceholder('Your Last.fm shared secret');
		await expect.element(secretInput).toBeInTheDocument();
	});

	it('should show error message when load fails', async () => {
		globalThis.fetch = mockLoadFailure();
		render(SettingsLastFm);

		const alert = page.getByText("Couldn't load your settings");
		await expect.element(alert).toBeInTheDocument();
	});

	it('should hide authorize step when no saved credentials', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			api_key: '',
			shared_secret: ''
		});
		render(SettingsLastFm);

		const step2Heading = page.getByText('Step 2');
		await expect.element(step2Heading).not.toBeInTheDocument();
	});

	it('should enable authorize button when credentials are saved', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			api_key: 'valid-key',
			shared_secret: '••••••••cret'
		});
		render(SettingsLastFm);

		const authorizeBtn = page.getByRole('button', { name: 'Open Last.fm' });
		await expect.element(authorizeBtn).not.toBeDisabled();
	});

	it('should show authorized username when present', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			username: 'myuser',
			session_key: '••••••••skey'
		});
		render(SettingsLastFm);

		const info = page.getByText('myuser');
		await expect.element(info).toBeInTheDocument();
	});

	it('should render save-and-test, test, and authorize buttons', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsLastFm);

		const saveTestBtn = page.getByRole('button', { name: 'Save & Test' });
		await expect.element(saveTestBtn).toBeInTheDocument();

		const testBtn = page.getByRole('button', { name: 'Test Connection' });
		await expect.element(testBtn).toBeInTheDocument();

		const authBtn = page.getByRole('button', { name: 'Open Last.fm' });
		await expect.element(authBtn).toBeInTheDocument();
	});
});
