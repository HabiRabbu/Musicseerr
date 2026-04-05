<script lang="ts">
	import type {
		LastFmConnectionSettingsResponse,
		LastFmAuthTokenResponse,
		LastFmAuthSessionResponse
	} from '$lib/types';
	import { api, ApiError } from '$lib/api/client';
	import { isAbortError } from '$lib/utils/errorHandling';
	import { createSettingsForm } from '$lib/utils/settingsForm.svelte';
	import { onMount, onDestroy } from 'svelte';
	import { ExternalLink, CircleCheck } from 'lucide-svelte';

	type ConnectionTestResult = { valid: boolean; message: string };

	const form = createSettingsForm<LastFmConnectionSettingsResponse>({
		loadEndpoint: '/api/v1/settings/lastfm',
		saveEndpoint: '/api/v1/settings/lastfm',
		testEndpoint: '/api/v1/settings/lastfm/verify',
		enabledField: 'enabled',
		refreshIntegration: true
	});

	let authorizing = $state(false);
	let exchanging = $state(false);
	let authResult: LastFmAuthSessionResponse | null = $state(null);
	let pendingToken = $state('');
	let showSecret = $state(false);
	let showDetails = $state(false);
	let credsPersisted = $state(false);
	const hasSavedCreds = $derived(
		credsPersisted && !!(form.data?.api_key && form.data?.shared_secret)
	);
	const testResult = $derived(form.testResult as ConnectionTestResult | null);

	const step1Complete = $derived(hasSavedCreds);
	const step2Complete = $derived.by(() => {
		if (!form.data) return false;
		return !!form.data.username && !!form.data.session_key;
	});
	const step3Complete = $derived.by(() => {
		if (!form.data) return false;
		return form.data.enabled;
	});
	const fullyConnected = $derived(step2Complete && step3Complete);
	const showForm = $derived(!fullyConnected || showDetails);

	export async function load() {
		await form.load();
		credsPersisted = !!(form.data?.api_key && form.data?.shared_secret);
	}

	async function save() {
		const ok = await form.save();
		if (ok && form.data?.api_key && form.data?.shared_secret) credsPersisted = true;
	}

	async function saveAndTest() {
		const ok = await form.save();
		if (ok) {
			if (form.data?.api_key && form.data?.shared_secret) credsPersisted = true;
			await form.test();
		}
	}

	async function test() {
		await form.test();
	}

	async function startAuth() {
		if (authorizing || exchanging) return;
		authorizing = true;
		authResult = null;
		pendingToken = '';
		try {
			const data = await api.global.post<LastFmAuthTokenResponse>('/api/v1/lastfm/auth/token');
			pendingToken = data.token;
			const authWindow = window.open(data.auth_url, '_blank', 'popup=yes,noopener,noreferrer');
			if (authWindow) authWindow.opener = null;
		} catch (error) {
			if (!isAbortError(error)) {
				authResult = {
					username: '',
					success: false,
					message: error instanceof ApiError ? error.message : "Couldn't start authorization"
				};
			}
		} finally {
			authorizing = false;
		}
	}

	async function completeAuth() {
		if (!pendingToken || exchanging) return;
		exchanging = true;
		authResult = null;
		try {
			const data = await api.global.post<LastFmAuthSessionResponse>('/api/v1/lastfm/auth/session', {
				token: pendingToken
			});
			authResult = data;
			if (form.data) {
				form.data = { ...form.data, username: data.username };
				await load();
			}
		} catch (error) {
			if (!isAbortError(error)) {
				authResult = {
					username: '',
					success: false,
					message: error instanceof ApiError ? error.message : "Couldn't finish authorization"
				};
			}
		} finally {
			exchanging = false;
			pendingToken = '';
		}
	}

	function cancelAuth() {
		pendingToken = '';
	}

	onMount(async () => {
		await form.load();
		credsPersisted = !!(form.data?.api_key && form.data?.shared_secret);
	});

	onDestroy(() => form.cleanup());
</script>

<div class="card bg-base-200">
	<div class="card-body">
		<h2 class="card-title text-2xl">Last.fm</h2>
		<p class="text-base-content/70 mb-4">
			Connect Last.fm to track listens and improve recommendations.
		</p>

		{#if form.loading}
			<div class="flex justify-center items-center py-12">
				<span class="loading loading-spinner loading-lg"></span>
			</div>
		{:else if form.data}
			<ul class="steps steps-horizontal w-full mb-6">
				<li class="step" class:step-primary={step1Complete}>API Credentials</li>
				<li class="step" class:step-primary={step2Complete}>Authorize</li>
				<li class="step" class:step-primary={step3Complete}>Enable</li>
			</ul>

			{#if fullyConnected}
				<div class="alert alert-success mb-4">
					<CircleCheck class="w-5 h-5 shrink-0" />
					<span>Connected as <strong>{form.data.username}</strong></span>
					<button
						type="button"
						class="btn btn-ghost btn-sm ml-auto"
						onclick={() => (showDetails = !showDetails)}
					>
						{showDetails ? 'Hide details' : 'Edit settings'}
					</button>
				</div>
			{/if}

			{#if showForm}
				<div class="space-y-6">
					<div class="space-y-4">
						<h3 class="text-lg font-semibold">Step 1 — API Credentials</h3>

						{#if !step1Complete}
							<div class="bg-base-300 rounded-lg p-4 space-y-2">
								<p class="text-sm font-medium">
									You will need a Last.fm API key and shared secret:
								</p>
								<ol class="list-decimal list-inside text-sm space-y-1 text-base-content/70">
									<li>
										<a
											href="https://www.last.fm/api/account/create"
											target="_blank"
											rel="noopener noreferrer"
											class="link link-primary inline-flex items-center gap-1"
										>
											Create a Last.fm API application
											<ExternalLink class="w-3 h-3" />
											<span class="sr-only">(opens in new tab)</span>
										</a>
									</li>
									<li>
										Copy the <strong>API Key</strong> and <strong>Shared Secret</strong> from that page
									</li>
									<li>Paste them here, then click <strong>Save &amp; Test</strong></li>
								</ol>
							</div>
						{/if}

						<div class="form-control w-full">
							<label class="label" for="lf-apikey">
								<span class="label-text">API Key</span>
							</label>
							<input
								id="lf-apikey"
								type="text"
								bind:value={form.data.api_key}
								class="input input-bordered w-full"
								placeholder="Your Last.fm API key"
							/>
							{#if step1Complete}
								<div class="label">
									<span class="label-text-alt text-base-content/50">
										Get credentials at <a
											href="https://www.last.fm/api/account/create"
											target="_blank"
											rel="noopener noreferrer"
											class="link link-primary"
											>last.fm/api<span class="sr-only"> (opens in new tab)</span></a
										>
									</span>
								</div>
							{/if}
						</div>

						<div class="form-control w-full">
							<label class="label" for="lf-secret">
								<span class="label-text">Shared Secret</span>
							</label>
							<div class="join w-full">
								<input
									id="lf-secret"
									type={showSecret ? 'text' : 'password'}
									bind:value={form.data.shared_secret}
									class="input input-bordered join-item flex-1"
									placeholder="Your Last.fm shared secret"
								/>
								<button
									type="button"
									class="btn join-item"
									onclick={() => (showSecret = !showSecret)}
								>
									{showSecret ? 'Hide' : 'Show'}
								</button>
							</div>
						</div>

						{#if testResult}
							<div
								class="alert"
								class:alert-success={testResult.valid}
								class:alert-error={!testResult.valid}
							>
								<span>{testResult.message}</span>
							</div>
						{/if}

						<div class="flex flex-wrap justify-end gap-2">
							<button
								type="button"
								class="btn btn-ghost"
								onclick={test}
								disabled={form.testing || form.saving || !form.data.api_key}
							>
								{#if form.testing && !form.saving}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Test Connection
							</button>
							<button
								type="button"
								class="btn btn-primary"
								onclick={saveAndTest}
								disabled={form.saving ||
									form.testing ||
									!form.data.api_key ||
									!form.data.shared_secret}
							>
								{#if form.saving}
									<span class="loading loading-spinner loading-sm"></span>
								{/if}
								Save &amp; Test
							</button>
						</div>
					</div>

					{#if step1Complete}
						<div class="divider"></div>
						<div class="space-y-4">
							<h3 class="text-lg font-semibold">Step 2 — Authorize</h3>

							{#if step2Complete && !pendingToken}
								<div class="alert alert-success">
									<CircleCheck class="w-5 h-5 shrink-0" />
									<span>Authorized as <strong>{form.data.username}</strong></span>
								</div>
								<button
									type="button"
									class="btn btn-outline btn-sm"
									onclick={startAuth}
									disabled={authorizing}
								>
									{#if authorizing}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									Re-authorize
								</button>
							{:else if !pendingToken}
								<p class="text-sm text-base-content/70">
									Open Last.fm in a new tab, approve access, then come back here.
								</p>
								<button
									type="button"
									class="btn btn-primary"
									onclick={startAuth}
									disabled={authorizing}
								>
									{#if authorizing}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									Open Last.fm
									<ExternalLink class="w-4 h-4" />
								</button>
							{/if}

							{#if pendingToken}
								<div class="card bg-base-300">
									<div class="card-body p-4 space-y-3">
										<p class="text-sm">
											Once you have approved access in Last.fm, finish the connection here.
										</p>
										<div class="flex gap-2">
											<button
												type="button"
												class="btn btn-primary btn-sm"
												onclick={completeAuth}
												disabled={exchanging}
											>
												{#if exchanging}
													<span class="loading loading-spinner loading-sm"></span>
												{/if}
												Complete Authorization
											</button>
											<button type="button" class="btn btn-ghost btn-sm" onclick={cancelAuth}
												>Cancel</button
											>
										</div>
									</div>
								</div>
							{/if}

							{#if authResult}
								<div
									class="alert"
									class:alert-success={authResult.success}
									class:alert-error={!authResult.success}
								>
									<span>{authResult.message}</span>
								</div>
							{/if}
						</div>
					{/if}

					{#if step2Complete || form.data.enabled}
						<div class="divider"></div>
						<div class="space-y-4">
							<h3 class="text-lg font-semibold">Step 3 — Enable</h3>

							<div class="form-control">
								<label class="label cursor-pointer justify-start gap-4">
									<input
										type="checkbox"
										bind:checked={form.data.enabled}
										class="toggle toggle-primary"
									/>
									<div>
										<span class="label-text font-medium">Enable Last.fm</span>
										<p class="text-xs text-base-content/50">
											{#if form.data.enabled && !step2Complete}
												Last.fm is turned on, but the account connection still needs to be finished.
											{:else}
												Use Last.fm for scrobbling, recommendations, and extra music details.
											{/if}
										</p>
									</div>
								</label>
							</div>

							<div class="flex justify-end pt-2">
								<button type="button" class="btn btn-primary" onclick={save} disabled={form.saving}>
									{#if form.saving}
										<span class="loading loading-spinner loading-sm"></span>
									{/if}
									Save Settings
								</button>
							</div>
						</div>
					{/if}

					{#if step3Complete}
						<div class="divider"></div>
						<div class="alert alert-info">
							<span>
								Want to scrobble to Last.fm too?
								<a href="/settings?tab=scrobbling" class="link font-medium"
									>Turn it on in the Scrobbling tab</a
								>
							</span>
						</div>
					{/if}
				</div>
			{/if}

			{#if form.message}
				<div
					class="alert mt-4"
					class:alert-success={form.messageType === 'success'}
					class:alert-error={form.messageType === 'error'}
				>
					<span>{form.message}</span>
				</div>
			{/if}
		{:else if form.message}
			<div class="alert" class:alert-error={form.messageType === 'error'}>
				<span>{form.message}</span>
			</div>
		{/if}
	</div>
</div>
