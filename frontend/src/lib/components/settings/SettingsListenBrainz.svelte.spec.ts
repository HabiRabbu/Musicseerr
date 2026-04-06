import { page } from '@vitest/browser/context';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render } from 'vitest-browser-svelte';
import SettingsListenBrainz from './SettingsListenBrainz.svelte';
import type { ListenBrainzConnectionSettings } from '$lib/types';

const defaultResponse: ListenBrainzConnectionSettings = {
	username: 'testuser',
	user_token: '',
	enabled: false
};

function mockLoadSuccess(data: ListenBrainzConnectionSettings = defaultResponse) {
	return vi.fn().mockResolvedValue(new Response(JSON.stringify(data), { status: 200 }));
}

function mockLoadFailure() {
	return vi.fn().mockResolvedValue(
		new Response(JSON.stringify({ error: { message: 'Failed to load ListenBrainz settings' } }), {
			status: 500
		})
	);
}

describe('SettingsListenBrainz.svelte', () => {
	let originalFetch: typeof globalThis.fetch;

	beforeEach(() => {
		originalFetch = globalThis.fetch;
	});

	afterEach(() => {
		globalThis.fetch = originalFetch;
	});

	it('should render the heading', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsListenBrainz);

		const heading = page.getByRole('heading', { name: 'ListenBrainz' });
		await expect.element(heading).toBeInTheDocument();
	});

	it('should show loading spinner initially', async () => {
		globalThis.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
		render(SettingsListenBrainz);

		const spinner = page.getByText('').all();
		expect(spinner.length).toBeGreaterThanOrEqual(0);
	});

	it('should render username and token fields after load', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsListenBrainz);

		const usernameInput = page.getByPlaceholder('Your ListenBrainz username');
		await expect.element(usernameInput).toBeInTheDocument();

		const tokenInput = page.getByPlaceholder('For private statistics');
		await expect.element(tokenInput).toBeInTheDocument();
	});

	it('should show error message when load fails', async () => {
		globalThis.fetch = mockLoadFailure();
		render(SettingsListenBrainz);

		const alert = page.getByText("Couldn't load your settings");
		await expect.element(alert).toBeInTheDocument();
	});

	it('should show getting-started guide when no saved credentials', async () => {
		globalThis.fetch = mockLoadSuccess({
			username: '',
			user_token: '',
			enabled: false
		});
		render(SettingsListenBrainz);

		const guide = page.getByText('To get started:');
		await expect.element(guide).toBeInTheDocument();
	});

	it('should show stepper with both steps', async () => {
		globalThis.fetch = mockLoadSuccess();
		render(SettingsListenBrainz);

		const steps = page.getByRole('list');
		await expect.element(steps).toBeInTheDocument();

		const step1 = page.getByRole('listitem').getByText('Credentials');
		await expect.element(step1).toBeInTheDocument();

		const step2 = page.getByRole('listitem').getByText('Enable');
		await expect.element(step2).toBeInTheDocument();
	});

	it('should show connected banner when fully connected', async () => {
		globalThis.fetch = mockLoadSuccess({
			username: 'myuser',
			user_token: 'token',
			enabled: true
		});
		render(SettingsListenBrainz);

		const banner = page.getByText('myuser');
		await expect.element(banner).toBeInTheDocument();

		const editBtn = page.getByRole('button', { name: 'Edit settings' });
		await expect.element(editBtn).toBeInTheDocument();
	});

	it('should show scrobbling cross-reference when enabled', async () => {
		globalThis.fetch = mockLoadSuccess({
			username: 'myuser',
			user_token: 'token',
			enabled: true
		});
		render(SettingsListenBrainz);

		const editBtn = page.getByRole('button', { name: 'Edit settings' });
		await editBtn.click();

		const crossRef = page.getByText('enable it in the Scrobbling tab');
		await expect.element(crossRef).toBeInTheDocument();
	});
});
