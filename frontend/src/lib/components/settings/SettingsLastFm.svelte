<script lang="ts">
	import type { LastFmConnectionSettingsResponse, LastFmAuthTokenResponse, LastFmAuthSessionResponse } from '$lib/types';
	import { throwOnApiError, handleFetchError } from '$lib/utils/errorHandling';
	import { onMount } from 'svelte';

	let connection: LastFmConnectionSettingsResponse | null = $state(null);
	let loading = $state(false);
	let saving = $state(false);
	let testing = $state(false);
	let authorizing = $state(false);
	let exchanging = $state(false);
	let message = $state('');
	let messageType = $state<'success' | 'error' | 'info'>('info');
	let testResult: { valid: boolean; message: string } | null = $state(null);
	let authResult: LastFmAuthSessionResponse | null = $state(null);
	let pendingToken = $state('');
	let showSecret = $state(false);
	let wasAlreadyEnabled = $state(false);
	let hasSavedCreds = $state(false);

	export async function load() {
		loading = true;
		message = '';
		try {
			const response = await fetch('/api/settings/lastfm');
			await throwOnApiError(response, 'Failed to load Last.fm settings');
			connection = await response.json();
			wasAlreadyEnabled = connection?.enabled ?? false;
			hasSavedCreds = !!(connection?.api_key && connection?.shared_secret);
		} catch (error) {
			message = handleFetchError(error, 'Failed to load Last.fm settings') ?? '';
			messageType = 'error';
		} finally {
			loading = false;
		}
	}

	async function save() {
		if (!connection) return;
		saving = true;
		message = '';
		try {
			const response = await fetch('/api/settings/lastfm', {
				method: 'PUT',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});
			await throwOnApiError(response, 'Failed to save settings');
			message = 'Last.fm settings saved successfully!';
			messageType = 'success';
			connection = await response.json();
			wasAlreadyEnabled = connection?.enabled ?? false;
			hasSavedCreds = !!(connection?.api_key && connection?.shared_secret);
			setTimeout(() => { message = ''; }, 5000);
		} catch (error) {
			message = handleFetchError(error, 'Failed to save settings') ?? '';
			messageType = 'error';
		} finally {
			saving = false;
		}
	}

	async function test() {
		if (!connection) return;
		testing = true;
		testResult = null;
		try {
			const response = await fetch('/api/settings/lastfm/verify', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify(connection)
			});
			await throwOnApiError(response, 'Validation failed');
			testResult = await response.json();
		} catch (error) {
			testResult = { valid: false, message: handleFetchError(error, 'Failed to test connection') ?? 'Failed to test connection' };
		} finally {
			testing = false;
		}
	}

	async function startAuth() {
		authorizing = true;
		authResult = null;
		pendingToken = '';
		try {
			const response = await fetch('/api/lastfm/auth/token', { method: 'POST' });
			await throwOnApiError(response, 'Failed to get auth token');
			const data: LastFmAuthTokenResponse = await response.json();
			pendingToken = data.token;
			window.open(data.auth_url, '_blank', 'noopener,noreferrer');
		} catch (error) {
			authResult = { username: '', success: false, message: handleFetchError(error, 'Failed to request authorization') ?? 'Failed to request authorization' };
		} finally {
			authorizing = false;
		}
	}

	async function completeAuth() {
		if (!pendingToken) return;
		exchanging = true;
		authResult = null;
		try {
			const response = await fetch('/api/lastfm/auth/session', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ token: pendingToken })
			});
			await throwOnApiError(response, 'Session exchange failed');
			const data: LastFmAuthSessionResponse = await response.json();
			authResult = data;
			if (connection) {
				connection = { ...connection, username: data.username };
				await load();
			}
		} catch (error) {
			authResult = { username: '', success: false, message: handleFetchError(error, 'Failed to complete authorization') ?? 'Failed to complete authorization' };
		} finally {
			exchanging = false;
			pendingToken = '';
		}
	}

	function cancelAuth() {
		pendingToken = '';
	}

	onMount(() => {
		load();
	});
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Last.fm</h2>
		<p class="text-base-content/70 mb-4">
			Connect to Last.fm for scrobbling and personalized music recommendations.
		</p>

		{#if loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if connection}
			<div class="space-y-4">
				<div class="form-control w-full">
					<label class="label" for="lf-apikey">
						<span class="label-text">API Key</span>
					</label>
					<input
						id="lf-apikey"
						type="text"
						bind:value={connection.api_key}
						class="input input-bordered w-full"
						placeholder="Your Last.fm API key"
					/>
					<p class="label">
						<span class="label-text-alt text-base-content/50">
							Get API credentials at <a href="https://www.last.fm/api/account/create" target="_blank" rel="noopener noreferrer" class="link link-primary">last.fm/api</a>
						</span>
					</p>
				</div>

				<div class="form-control w-full">
					<label class="label" for="lf-secret">
						<span class="label-text">Shared Secret</span>
					</label>
					<div class="join w-full">
						<input
							id="lf-secret"
							type={showSecret ? 'text' : 'password'}
							bind:value={connection.shared_secret}
							class="input input-bordered join-item flex-1"
							placeholder="Your Last.fm shared secret"
						/>
						<button type="button" class="btn join-item" onclick={() => showSecret = !showSecret}>
							{showSecret ? 'Hide' : 'Show'}
						</button>
					</div>
				</div>

				{#if testResult}
					<div class="alert" class:alert-success={testResult.valid} class:alert-error={!testResult.valid}>
						<span>{testResult.message}</span>
					</div>
				{/if}

				{#if connection.username}
					<div class="alert alert-info">
						<span>Authorized as <strong>{connection.username}</strong></span>
					</div>
				{/if}

				{#if pendingToken}
					<div class="card bg-base-300">
						<div class="card-body p-4 space-y-3">
							<p class="text-sm">
								A Last.fm authorization page has been opened. Please authorize access there, then click the button below.
							</p>
							<div class="flex gap-2">
								<button type="button" class="btn btn-primary btn-sm" onclick={completeAuth} disabled={exchanging}>
									{#if exchanging}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									I've Authorized
								</button>
								<button type="button" class="btn btn-ghost btn-sm" onclick={cancelAuth}>Cancel</button>
							</div>
						</div>
					</div>
				{/if}

				{#if authResult}
					<div class="alert" class:alert-success={authResult.success} class:alert-error={!authResult.success}>
						<span>{authResult.message}</span>
					</div>
				{/if}

				<div class="form-control">
					<label class="label cursor-pointer justify-start gap-4">
						<input
							type="checkbox"
							bind:checked={connection.enabled}
							class="toggle toggle-primary"
							disabled={!testResult?.valid && !wasAlreadyEnabled}
						/>
						<div>
							<span class="label-text font-medium">Enable Last.fm Integration</span>
							<p class="text-xs text-base-content/50">
								{#if !testResult?.valid && !wasAlreadyEnabled}
									Test connection first to enable
								{:else}
									Enable Last.fm features like scrobbling and recommendations
								{/if}
							</p>
						</div>
					</label>
				</div>

				{#if message}
					<div class="alert" class:alert-success={messageType === 'success'} class:alert-error={messageType === 'error'}>
						<span>{message}</span>
					</div>
				{/if}

				<div class="flex flex-wrap justify-end gap-2 pt-2">
					<button
						type="button"
						class="btn btn-ghost"
						onclick={startAuth}
						disabled={authorizing || !hasSavedCreds || !!pendingToken}
					>
						{#if authorizing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Authorize
					</button>
					<button type="button" class="btn btn-ghost" onclick={test} disabled={testing || !connection.api_key}>
						{#if testing}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Test Connection
					</button>
					<button type="button" class="btn btn-primary" onclick={save} disabled={saving}>
						{#if saving}
							<span class="loading loading-spinner loading-sm"></span>
						{/if}
						Save Settings
					</button>
				</div>
			</div>
		{:else if message}
			<div class="alert" class:alert-error={messageType === 'error'}>
				<span>{message}</span>
			</div>
		{/if}
	</div>
</div>
