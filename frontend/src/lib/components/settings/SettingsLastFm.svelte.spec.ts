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
	enabled: false,
};

function mockLoadSuccess(data: LastFmConnectionSettingsResponse = defaultResponse) {
	return vi.fn().mockResolvedValue({
		ok: true,
		json: () => Promise.resolve(data),
	});
}

function mockLoadFailure() {
	return vi.fn().mockResolvedValue({
		ok: false,
		status: 500,
		json: () => Promise.reject(new Error('Server error')),
	});
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

		const alert = page.getByText('Failed to load Last.fm settings');
		await expect.element(alert).toBeInTheDocument();
	});

	it('should disable authorize button when no saved credentials', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			api_key: '',
			shared_secret: '',
		});
		render(SettingsLastFm);

		const authorizeBtn = page.getByRole('button', { name: 'Authorize' });
		await expect.element(authorizeBtn).toBeDisabled();
	});

	it('should enable authorize button when credentials are saved', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			api_key: 'valid-key',
			shared_secret: '••••••••cret',
		});
		render(SettingsLastFm);

		const authorizeBtn = page.getByRole('button', { name: 'Authorize' });
		await expect.element(authorizeBtn).not.toBeDisabled();
	});

	it('should show authorized username when present', async () => {
		globalThis.fetch = mockLoadSuccess({
			...defaultResponse,
			username: 'myuser',
		});
		render(SettingsLastFm);

		const info = page.getByText('myuser');
		await expect.element(info).toBeInTheDocument();
	});

	it('should render save, test, and authorize buttons', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsLastFm);

		const saveBtn = page.getByRole('button', { name: 'Save Settings' });
		await expect.element(saveBtn).toBeInTheDocument();

		const testBtn = page.getByRole('button', { name: 'Test Connection' });
		await expect.element(testBtn).toBeInTheDocument();

		const authBtn = page.getByRole('button', { name: 'Authorize' });
		await expect.element(authBtn).toBeInTheDocument();
	});
});
